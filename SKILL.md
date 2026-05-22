---
name: claw-skills
description: Skill bundle — stepfun-image, stepfun-tts, and stepfun-asr for zeroclaw agents.
---

# Claw Skills

A collection of reusable skills for zeroclaw agents:

- **stepfun-image** — Generate and edit images via StepFun Image API
- **stepfun-tts** — Text-to-speech synthesis via StepFun TTS API
- **stepfun-asr** — Speech recognition via StepFun ASR API

## Install

```bash
# Whole bundle (requires root SKILL.md for audit)
zeroclaw skills install https://github.com/furylachori/choriskills.git

# Individual skills from local clone
git clone https://github.com/furylachori/choriskills.git
zeroclaw skills install ./choriskills/stepfun-image
zeroclaw skills install ./choriskills/stepfun-tts
zeroclaw skills install ./choriskills/stepfun-asr
```

All scripts require `STEPFUN_API_KEY` in the environment.
