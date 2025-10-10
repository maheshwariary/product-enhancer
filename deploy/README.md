# 🚀 Clio AI - Deployment Guide

Complete guide to deploy Clio AI to AWS AgentCore.

---

## 📋 Prerequisites

### Required Software

1. **Docker Desktop**
   - Download: https://www.docker.com/products/docker-desktop/
   - After install: Settings → General → Enable "Use WSL 2 based engine"
   - Enable ARM64 support: Settings → Docker Engine

2. **AWS CLI v2**
   - Download: https://aws.amazon.com/cli/
   - Verify: `aws --version`

3. **Git Bash** (Windows)
   - Download: https://git-scm.com/downloads
   - Required to run deploy.sh

### AWS Setup

1. **Configure AWS Credentials:**
```bash
   aws configure