# Sends the prompt + one transcript to each model through OpenRouter.
# Put the LLMREI interview files (.json) in a folder called "interviews" next to this file.
# Each response is saved in its own folder inside "outputs", as response.txt and log.txt.
# If a response fails or is cut off, run the file again. Saved responses are skipped.
#
# The OpenRouter parts follow their documentation:
#   https://openrouter.ai/docs/quickstart
#   https://openrouter.ai/docs/api_reference/responses/basic-usage
#   https://openrouter.ai/docs/api/api-reference/responses/create-a-response

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

folder = Path(__file__).resolve().parent
interviews_folder = folder / "interviews"
output_folder = folder / "outputs"

# same prompt for all models, the transcript is added after "Transcript:"
prompt_text = """You are a requirements reviewer. Below is the transcript of a requirements elicitation interview between an interviewer and a stakeholder. Review the transcript and write the software requirements for the system the stakeholder needs.

Transcript:
"""

# models to compare
models = {
    "claude": "anthropic/claude-opus-5.5-20260921",
    "gpt": "openai/gpt-6.1-sol-20260929",
    "gemini": "google/gemini-4-argon",
}

max_tokens = 32000

# OpenRouter client (OpenAI SDK example in the quickstart)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

for alias in models:
    for interview_file in sorted(interviews_folder.glob("*.json")):
        # one folder per response, named after the interview
        reply_folder = output_folder / alias / interview_file.stem
        reply_file = reply_folder / "response.txt"
        reply_log = reply_folder / "log.txt"
        if reply_file.exists():
            continue  # skip, this response was saved in an earlier run

        # build the transcript from the interview file: put the messages in order,
        # leave out the interviewer's instructions (type 0), and label who is speaking
        interview = json.loads(interview_file.read_text(encoding="utf-8"))
        messages = sorted(interview["messages"], key=lambda m: m["position"])
        turns = []
        for m in messages:
            if m["message_type"] == 1:
                turns.append("Interviewer: " + m["message_text"])
            elif m["message_type"] == 2:
                turns.append("Stakeholder: " + m["message_text"])
        transcript = "\n\n".join(turns)
        prompt = prompt_text + transcript

        # send the request (quickstart), with the output limit (Basic Usage page)
        response = client.responses.create(
            model=models[alias],
            input=prompt,
            max_output_tokens=max_tokens,
        )

        text = response.output_text
        reply_folder.mkdir(parents=True, exist_ok=True)

        # save the response only if it is complete and not empty,
        # otherwise it is requested again in the next run
        if response.status != "completed":
            status = "cut off"
        elif text.strip() == "":
            status = "empty"
        else:
            status = "ok"
            reply_file.write_text(text, encoding="utf-8")

        # write the log for this response
        log_lines = [
            "time_utc: " + datetime.now(timezone.utc).isoformat(),
            "model_alias: " + alias,
            "model_requested: " + models[alias],
            "model_returned: " + str(response.model),
            "interview: " + interview_file.name,
            "status: " + status,
            "input_tokens: " + str(response.usage.input_tokens),
            "output_tokens: " + str(response.usage.output_tokens),
        ]
        reply_log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        print(alias, interview_file.name, status)

# before running, in the same terminal:
# If Windows (PowerShell), run: $env:OPENROUTER_API_KEY = "your-key-here"
# If Mac or Linux, run: export OPENROUTER_API_KEY="your-key-here"
# Then run python call_llm.py from that terminal. The setting lasts until you close it.

