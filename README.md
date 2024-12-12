# Supagrants

Supagrants is a Telegram-based AI assistant designed to help users discover and apply for grants. It streamlines the grant application process by gathering project information, matching projects with relevant grants, and providing AI-generated suggestions to enhance applications.

## Features
•	Project Information Collection: Submit project details, including document links, GitHub repositories, and PDFs, directly through Telegram.
•	Automated Data Processing: The bot processes submitted documents and repositories to build a comprehensive project profile.
•	Grant Matching: Receive matches with suitable grants based on your project’s profile.
•	Application Assistance: Benefit from AI-generated suggestions to improve your grant applications.
•	Status Monitoring: Easily query the status of your applications and view your project profiles at any time.

## Sprint Plan

**Day 0: Backend and Telegram Bot Setup**
- **TG:** Develop a basic Telegram bot using the `python-telegram-bot` library and test responsiveness.

**Day 1: User Input Handling**
- **BE:** Implement functionality for users to submit project details (e.g., document links, GitHub repositories, PDFs) and store them in MongoDB.

**Day 2: Data Processing Tools**
- **BE:** Create a tool to process PDFs, extracting text using libraries like PyMuPDF.
- **BE:** Develop a crawler to visit provided documentation links and cache data using Beautiful Soup.
- **BE:** Implement a module to extract data from GitHub repositories using PyDriller.

**Day 3: Interactive Features**
- **BE:** Design prompts for the bot to gather additional project information dynamically.
- **BE:** Develop features to track and allow users to query the status of their applications via the bot.

**Day 4: Profile Access and Grant Matching**
- **TG:** Enable users to access and review their project profiles through bot commands or buttons.
- **BE:** Design and integrate an algorithm to match projects with relevant grants.

**Day 5: AI Assistance and Persona Development**
- **TG:** Display matched grants to users through the Telegram bot interface, enabling interaction.
- **BE:** Integrate AI models to provide users with suggestions for completing grant applications.
- **BE:** Develop a persona and style for the AI agent to ensure consistent and engaging interactions.

**Day 6: Landing Page and Backend Orchestration**
- **FE:** Design and develop a landing page introducing Supagrants, incorporating cohesive branding elements.
- **BE:** Utilize PhiData to orchestrate backend processes, ensuring seamless component integration.

**Day 7: Quality Assurance and Documentation**
- **QA:** Perform continuous testing and debugging throughout development to maintain quality.
- **DOC:** Document all features, codebases, and processes for future reference and onboarding.