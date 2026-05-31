---
name: claw-skills
description: Skill bundle — stepfun-image, stepfun-tts, stepfun-asr, bailian-image, and minimax-video for zeroclaw agents.
---

# Claw Skills

A collection of reusable skills for zeroclaw agents:

- **stepfun-image** — Generate and edit images via StepFun Image API
- **stepfun-tts** — Text-to-speech synthesis via StepFun TTS API
- **stepfun-asr** — Speech recognition via StepFun ASR API
- **bailian-image** — Generate images via Bailian (Alibaba Cloud) Image API
- **minimax-video** — Generate videos via MiniMax Video API

## Install

```bash
# Whole bundle (requires root SKILL.md for audit)
zeroclaw skills install https://github.com/furylachori/choriskills.git

# Individual skills from local clone
git clone https://github.com/furylachori/choriskills.git
zeroclaw skills install ./choriskills/stepfun-image
zeroclaw skills install ./choriskills/stepfun-tts
zeroclaw skills install ./choriskills/stepfun-asr
zeroclaw skills install ./choriskills/bailian-image
zeroclaw skills install ./choriskills/minimax-video
```

Environment variables required per skill:

| Skill | API Key |
|-------|---------|
| stepfun-image, stepfun-tts, stepfun-asr | `STEPFUN_API_KEY` |
| bailian-image | `BAILIAN_TOKEN_PLAN_API_KEY` |
| minimax-video | `MINIMAX_API_KEY` |
