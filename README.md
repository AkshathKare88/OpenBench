# OpenBench — Trusted Campus Resource Sharing

OpenBench is a runnable hackathon prototype for discovering and responsibly sharing underused campus spaces and equipment. It includes resource listings, training-aware booking requests, owner decisions, check-in and return condition records, incident reporting, role-scoped audit views, a fair-use cap, and catalogue search and filtering.

> **Demo limitations:** The sign-in flow switches between fictional demo profiles; it is not real authentication. Use fictional data only. This project is intended for local demonstration and hackathon evaluation, not real institutional access decisions or sensitive information without proper authentication, security and privacy reviews, and operational safeguards.

## Run Locally

**Requirements:** Python 3.11 or later.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser. The app seeds fictional demo accounts and resources on first launch.

## Demo Accounts

Use the in-app demo sign-in to switch between these fictional profiles:

- **Aarav Demo Student** — electronics and 3D-printer training recorded.
- **Mira Demo Student** — no specialist training recorded.
- **Lab Manager Demo** — lists resources and reviews bookings for resources they own.
- **Platform Admin Demo** — global review access.

These are demonstration profiles, not real user accounts. Do not enter real passwords or sensitive personal information.

## Features

- Resource catalogue with search, category, and availability filters.
- Training-aware booking eligibility.
- Booking requests, owner decisions, and overlapping-slot conflict checks.
- Fair-use cap of two active requests/bookings per student.
- Check-in and return with before-and-after condition records.
- Incident reporting and resolution notes.
- Role-scoped audit views and event history.

## Automated Tests

Install the project dependencies, then run:

```bash
python -m unittest discover -s tests -v
```

The included regression tests cover student access to the audit page, owner restrictions when reviewing another owner's booking, overlapping booking approvals, owner-scoped incident visibility, and keeping a resource unavailable while another damage incident remains open. The tests use a temporary database.

Run the tests in your own environment before submitting. The test suite is included in this project, but inclusion alone does not mean the tests have passed.

## Suggested Judge Demo

1. Explore the resource catalogue and try the search, category, and availability filters.
2. Open **Digital Oscilloscope**, switch to **Mira Demo Student**, and demonstrate how training eligibility prevents an ineligible booking request.
3. Switch to **Aarav Demo Student** and submit a request for a future time slot.
4. Switch to **Lab Manager Demo** and review the request. Test an overlapping request to demonstrate conflict prevention.
5. Switch back to Aarav, check out with initial condition notes, and record the return condition.
6. Submit a fictional damage incident.
7. Switch to Lab Manager, open **Trust & audit**, review the incident, resolve it with a note, and inspect the event history.

Only demonstrate behavior that you have personally verified. Reset or prepare the demo data before the presentation so the workflow is easy to follow.

## Deployment Notes

The Flask application exposes `app` for a WSGI server. The project requirements include Gunicorn; after installing the dependencies, a compatible host can start the app with:

```bash
gunicorn app:app
```

For a host with a persistent filesystem, set `SECRET_KEY` to a strong random value and optionally set `DATABASE_PATH` to a persistent SQLite file path. If the host has an ephemeral filesystem, use a persistent disk or a managed database. Set `COOKIE_SECURE=1` only when serving over HTTPS.

Before any public or real-world deployment, replace demo account switching with real authentication; review authorization and add appropriate CSRF protection; verify training and identity through trusted systems where appropriate; review time zones and institutional calendars; implement backups and monitoring; and security-test the complete application. Do not use the demo sign-in mechanism to protect real institutional resources or sensitive information.

## Team Contributions

We collaborated throughout the development of OpenBench, sharing ideas, reviewing the implementation, and testing the application together. Our primary areas of responsibility were divided as follows:

- **Akshath — Backend and Integration:** Coordinated application integration, worked on the Flask backend and booking workflow, and helped test end-to-end functionality.
- **Pranathi — Frontend and Resource Discovery:** Worked on the user interface, resource catalogue, search and filtering, and improving the overall user experience.
- **Lalitha — Trust, Safety, and Testing:** Worked on check-in and return condition records, incident reporting, audit history, and testing role-specific workflows.

All three team members contributed to reviewing and testing the overall application. These responsibilities describe our intended division of work and should be adjusted if our actual contributions differed.

**AI Assistance:** AI tools were used to assist with parts of development and documentation. The team reviewed the resulting work and tested the application, with the extent of AI assistance disclosed in accordance with the hackathon rules.

## Technology Stack

Python, Flask, SQLite, Jinja templates, HTML, CSS, and JavaScript.
