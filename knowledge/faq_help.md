# FAQ — Sky Assistant Help

## How do I start the demo without an account?
On the login page, choose Continue as Demo Operator. This creates a temporary session for the Control Tower hackathon demo without signup.

## Which APIs power the Control Tower?
Authenticated session users can call /api/fleet/dashboard, /vehicles, /orders, /optimize, /plans/<id>/apply, /events, /recovery, /decisions, /impact, /copilot, /reset-demo, and /api/help/chat for RAG-assisted Q&A.

## Do I need Gemini or OpenAI?
No. Routing, cost, and emissions are computed by OR-Tools and formulas. LLM keys are optional for richer natural-language answers. Without keys, the assistant uses RAG knowledge docs plus structured tools.

## Voice commands
Fleet Copilot and Sky Assistant support free voice input through the browser Web Speech API (Chrome or Edge). Tap the microphone, speak, and the transcript is sent as a command. Local Whisper is optional later if offline transcription is required — not needed for the hackathon demo.

## Why can't I mutate the fleet while logged out?
Fleet mutation endpoints require a session (login or demo guest) so judges share a controlled demo and anonymous visitors cannot reset or disrupt state.

## What is RAG in Sky.EcoAI?
Retrieval-Augmented Generation pulls relevant operator guide / recovery playbook chunks and live fleet KPIs into the assistant prompt before answering, so responses stay grounded in product knowledge and current state—not hallucinated numbers.

## Map not updating?
Apply a plan first. Routes appear as polylines after Optimization Studio apply or recovery apply. Use Reset demo if state is messy.

## Support vs Fleet Copilot
Support tickets are for account issues. Fleet Copilot and the floating Sky Assistant are for operational questions, plan explanations, and triggering confirmed actions (optimize, breakdown simulation, recovery).
