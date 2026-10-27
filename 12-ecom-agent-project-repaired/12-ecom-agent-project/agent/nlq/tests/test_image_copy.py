"""Docker-free copy, Docker Hub -> ECR, against a stand-in Docker Hub (the real registry protocol over
httpx.MockTransport) and a stand-in ECR that records the boto3 calls."""
import hashlib
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra import image_copy  # noqa: E402


def digest(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


CONFIG, L1, L2 = b'{"architecture":"arm64"}', b"layer-one" * 1000, b"layer-two" * 50
ARM = json.dumps({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                  "config": {"digest": digest(CONFIG), "size": len(CONFIG)},
                  "layers": [{"digest": digest(L1), "size": len(L1)}, {"digest": digest(L2), "size": len(L2)}]}).encode()
INDEX = json.dumps({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json", "manifests": [
    {"digest": "sha256:" + "a" * 64, "platform": {"os": "linux", "architecture": "amd64"}},
    {"digest": digest(ARM), "platform": {"os": "linux", "architecture": "arm64"}},
    {"digest": "sha256:" + "b" * 64, "platform": {"os": "unknown", "architecture": "unknown"}}]}).encode()


def hub(manifests: dict, blobs: dict):
    def handler(req: httpx.Request):
        if req.url.host == "auth.docker.io":
            return httpx.Response(200, json={"token": "t"})
        assert req.headers["authorization"] == "Bearer t"
        path = req.url.path
        if "/manifests/" in path:
            ref = path.rsplit("/", 1)[1]
            if ref not in manifests:
                return httpx.Response(404)
            body, media = manifests[ref]
            return httpx.Response(200, content=body, headers={"content-type": media})
        return httpx.Response(200, content=blobs[path.rsplit("/", 1)[1]])
    return httpx.Client(transport=httpx.MockTransport(handler))


class FakeECR:
    class exceptions:
        class LayerAlreadyExistsException(Exception): pass
        class ImageAlreadyExistsException(Exception): pass

    def __init__(self, present=()):
        self.present, self.layers, self.parts, self.images, self.uploads = set(present), {}, [], [], {}

    def batch_check_layer_availability(self, repositoryName, layerDigests):
        return {"layers": [{"layerDigest": d, "layerAvailability": "AVAILABLE"} for d in layerDigests if d in self.present]}

    def initiate_layer_upload(self, repositoryName):
        uid = f"u{len(self.uploads)}"
        self.uploads[uid] = b""
        return {"uploadId": uid}

    def upload_layer_part(self, repositoryName, uploadId, partFirstByte, partLastByte, layerPartBlob):
        assert partFirstByte == len(self.uploads[uploadId]) and partLastByte - partFirstByte + 1 == len(layerPartBlob)
        self.uploads[uploadId] += layerPartBlob
        self.parts.append(uploadId)

    def complete_layer_upload(self, repositoryName, uploadId, layerDigests):
        assert digest(self.uploads[uploadId]) == layerDigests[0]          # ECR checks the digest too
        self.layers[layerDigests[0]] = self.uploads[uploadId]

    def put_image(self, **kw):
        self.images.append(kw)


REPO = "234360896963.dkr.ecr.us-east-1.amazonaws.com/ecom-nlq-agent"
BLOBS = {digest(CONFIG): CONFIG, digest(L1): L1, digest(L2): L2}


def test_multi_platform_copies_arm64_only(monkeypatch):
    monkeypatch.setattr(image_copy, "PART", 4000)                         # force a multi-part upload
    ecr = FakeECR(present={digest(L2)})                                     # one layer already in ECR
    http = hub({"1.0": (INDEX, "application/vnd.oci.image.index.v1+json"),
                digest(ARM): (ARM, "application/vnd.oci.image.manifest.v1+json")}, BLOBS)
    uri = image_copy.copy("prudhvi/ecom-nlq-agent:1.0", REPO, "us-east-1", http=http, ecr=ecr)
    assert uri == f"{REPO}:latest"
    assert set(ecr.layers) == {digest(CONFIG), digest(L1)}                  # L2 skipped
    assert ecr.layers[digest(L1)] == L1 and len([p for p in ecr.parts]) > 2  # L1 (9,000 bytes) in 3 parts
    img = ecr.images[0]
    assert img["imageManifest"].encode() == ARM and img["imageTag"] == "latest"   # exact bytes: same digest
    assert img["imageManifestMediaType"] == "application/vnd.oci.image.manifest.v1+json"


def test_corrupt_download_never_reaches_ecr():
    ecr = FakeECR()
    bad = dict(BLOBS)
    bad[digest(L1)] = b"tampered"
    http = hub({"1.0": (ARM, "application/vnd.oci.image.manifest.v1+json")}, bad)
    with pytest.raises(SystemExit, match="failed its checksum"):
        image_copy.copy("prudhvi/ecom-nlq-agent:1.0", REPO, http=http, ecr=ecr)
    assert digest(L1) not in ecr.layers and ecr.images == []


def test_no_arm64_build_is_explained():
    amd_only = json.dumps({"manifests": [{"digest": "sha256:" + "a" * 64, "platform": {"os": "linux", "architecture": "amd64"}}]}).encode()
    http = hub({"1.0": (amd_only, "application/vnd.oci.image.index.v1+json")}, {})
    with pytest.raises(SystemExit, match=r"no linux/arm64 image \(found: \['linux/amd64'\]\)"):
        image_copy.copy("prudhvi/x:1.0", REPO, http=http, ecr=FakeECR())


def test_single_platform_and_not_found():
    ecr = FakeECR()
    http = hub({"1.0": (ARM, "application/vnd.oci.image.manifest.v1+json")}, BLOBS)
    image_copy.copy("prudhvi/ecom-nlq-agent:1.0", REPO, http=http, ecr=ecr)
    assert len(ecr.layers) == 3 and ecr.images
    with pytest.raises(SystemExit, match="not found on Docker Hub"):
        image_copy.copy("prudhvi/typo:1.0", REPO, http=hub({}, {}), ecr=FakeECR())


def test_parse():
    assert image_copy.parse("prudhvi/ecom-nlq-agent:1.0") == ("prudhvi/ecom-nlq-agent", "1.0")
    assert image_copy.parse("docker.io/prudhvi/ecom-nlq-agent") == ("prudhvi/ecom-nlq-agent", "latest")
    assert image_copy.parse("python:3.12") == ("library/python", "3.12")
