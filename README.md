# roast-my-code

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

The AI that roasts your codebase so your teammates don't have to.

## Install

```bash
pip install roast-my-code
```

## Free LLM Setup (Recommended)

Use Groq as primary (free tier), and NVIDIA NIM as backup.

```bash
export GROQ_API_KEY="your-groq-key"
export NVIDIA_NIM_API_KEY="your-nim-key"
```

Default model choices in this project:
- Primary: `llama-3.3-70b-versatile` (Groq)
- Backup: `microsoft/phi-4-mini-instruct` (NIM)

## Usage

```bash
roast ./my-project
roast https://github.com/user/repo
roast ./my-project --no-llm --output report.html
```

Provider controls:

```bash
roast ./my-project --provider groq --model llama-3.3-70b-versatile
roast ./my-project --provider auto --backup-provider nim --backup-model microsoft/phi-4-mini-instruct
```

## Demo

[demo.gif]

## Contributing

Contributions are welcome. Open an issue for bugs/ideas, then submit a PR with tests for behavior changes.