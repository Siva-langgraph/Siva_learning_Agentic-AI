---
name: ecom-publish-images
description: Instructor task — build the three e-commerce agent images (nlq, chart_gen, supervisor) for linux/arm64, push them to Docker Hub, and prove students can pull them anonymously. Use when publishing a new version for students or when a student's --image deploy cannot find an image.
---

# Publish the e-commerce images to Docker Hub

```
publish_images.py --user <hub-user> --tag <version>
   for nlq · chart_gen · supervisor
     STEP 1  agent/<name>/deploy.py --publish        docker buildx, linux/arm64, push
     STEP 2  anonymous pull of the arm64 manifest    what a student's --image does first
   summary: OK / FAILED per image + the student commands
```

| Component | Image |
|---|---|
| nlq | `<user>/ecom-nlq-agent:<tag>` |
| chart_gen | `<user>/ecom-chart-gen-agent:<tag>` |
| supervisor | `<user>/ecom-supervisor-agent:<tag>` |

The web app runs locally and has no image.

## Run — Docker Desktop running

**Mac**
```bash
docker login
cd ~/PycharmProjects/vs-langchain-agents/12-ecom-agent-project
python publish_images.py --user prudhviakella898 --tag 1.0
```

**Windows**
```powershell
docker login
cd $HOME\PycharmProjects\vs-langchain-agents\12-ecom-agent-project
python publish_images.py --user prudhviakella898 --tag 1.0
```

One component again: `--only supervisor` (names: `nlq`, `chart_gen`, `supervisor`).

## Rules

1. A new tag for every release; never overwrite a tag students deployed.
2. Repositories must be public — STEP 2 reports a private one as FAILED.
3. Publishing changes nothing in AWS. The e-commerce `--publish` still checks your AWS login
   first.
4. After publishing, update the tag in the `ecom-deploy-agents` skill.

Students deploy with `deploy.py --image <user>/<image>:<tag>`; the image is copied into their
own ECR over HTTPS (`infra/image_copy.py`), so they need no Docker — only `pip install httpx`.
