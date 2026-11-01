# AWS Architect Simulator — Local MVP

A local Flask application for practicing customer discovery and AWS solution design.

## Run in PyCharm
1. Extract this ZIP to `~/PycharmProjects/aws_architect_simulator`.
2. Open the folder in PyCharm and configure a Python 3.10+ interpreter.
3. Open the PyCharm terminal and run `python -m pip install -r requirements.txt`.
4. Run `app.py` with PyCharm's Run button, or execute `python app.py`.
5. Open http://127.0.0.1:5000 in your browser.

Stop the server with Ctrl+C.

## Included
- Dark, visual dashboard and healthcare customer scenario.
- Branching discovery questions with saved answers during the session.
- Selectable AWS service catalog.
- SVG diagram that updates when services are selected.
- Rule-based review, missing core services, bonus services, and architecture validation reminders.
- SQLite training history stored in `simulator.db`.

## Notes
This is a learning prototype, not an official AWS product. It creates no AWS resources. Scores are based on simple hand-authored rules and are not authoritative architecture advice. The diagram is illustrative and not deployment-validated. Verify real architecture decisions, security controls, service compatibility, and costs against current AWS documentation. No AI API is connected yet; customer answers are curated.
