Always write code in a clean and organized matter, implementing the best practices from the Clean Code book.
Test driven development for everything. Think about the design, what tests are needed, and write tests before implementing code. Make sure tests run as you move through each task.
For large, risky, hardware-facing, or multi-turn implementation tasks, document progress in a markdown file under `progress/`, dated to the current date. Small localized edits do not need a progress file unless it helps handoff.
When planning, make sure to ask follow up questions to confirm that everything I want in the plan I get down. 
When a progress file is warranted, include what work was done, issues found/resolved, validation run, hardware impact, and next steps.
For hardware-facing changes, use this validation order: first run focused offline/unit tests, then stop and give me the exact hardware test procedure before cleanup or broad test sweeps. After I run/confirm hardware tests or tell you to continue, clean up and run the broader relevant tests.
Make sure to clean up after yourself. Delete any files that are no longer needed. For example, if you write a test_s3_connection.py to verify s3 connectivity but we don't need it for later, delete it. Same goes with planning markdown files.
Always write clean code, using the principles from the book "Clean Code" by Robert Martin.
When you finish a task that has a progress file, update it or delete it after durable notes have moved into docs/PRs.
If the task makes a fundamental change (i.e. you add a new command line argument, you add a brand new feature) make sure to add it to AGENTS.md and README.md such that another agent or human can understand for context easily if changes need to be made.
Always create a plan that I will review before executing when in planning mode.

Agent retrieval rule: before coding, read `AGENTS.md` and use `docs/agent-index.md` to retrieve only the specific source/docs needed for the subsystem you are touching. Prefer repo-grounded reasoning over model memory for CubOS semantics, especially hardware motion, coordinate frames, YAML schema, validation, and protocol setup.
