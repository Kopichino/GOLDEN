# GOLDEN: Complete Setup & Running Guide

This guide is for anyone pulling this repository from GitHub who wants to get the entire project up and running from scratch on a clean machine.

---

## 💡 Quick Conceptual Clarification: Where is the Database & Data?

If you are wondering:
> *"Where is the FHIR server? Did I download it? Where is the `data` folder?"*

Here is how it actually works:
1. **No local `data` folder is required.** You did not miss downloading any data folder, and Git did not omit any files.
2. **HAPI FHIR runs in Docker**: In [docker-compose.yml](file:///d:/College/SEM7/AD/docker-compose.yml), we specify `image: hapiproject/hapi:latest`. When you run `docker compose up -d`, Docker **automatically downloads** the entire FHIR server software directly from Docker Hub over the internet and runs it inside a secure virtual container on port `8080`.
3. **Where the patients/hospitals come from**: They are generated programmatically by running [scripts/seed_synthea.py](file:///d:/College/SEM7/AD/scripts/seed_synthea.py). This script connects to `http://localhost:8080/fhir` and uploads synthetic Indian emergency hospitals and patient profiles directly into the running FHIR server.

---

## 📋 Prerequisites

Before starting, ensure you have the following installed on your machine:
1. **Git**: [https://git-scm.com/](https://git-scm.com/)
2. **Python 3.11 or 3.12**: [https://www.python.org/downloads/](https://www.python.org/downloads/)
3. **Docker Desktop**: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) *(Mandatory for running the local HAPI FHIR healthcare database)*
4. **An API Key** (Free tier):
   - A free **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/) *(Recommended)*  
     *OR*
   - A free **Groq API Key** from [Groq Cloud Console](https://console.groq.com/)

---

## 🚀 Step-by-Step Setup Instructions

### Step 1: Clone the Repository
Open PowerShell or your terminal:
```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

---

### Step 2: Set Up Python Virtual Environment

#### Option A: Using Standard Python Virtual Environment (Recommended)
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# (If PowerShell blocks script execution, run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)

# On Mac/Linux:
source .venv/bin/activate
```

#### Option B: Using Conda
```powershell
conda create -n golden python=3.12 -y
conda activate golden
```

---

### Step 3: Install Python Dependencies
Install all required libraries specified in `requirements.txt`:
```powershell
pip install -r requirements.txt
```

---

### Step 4: Configure Environment Variables (`.env`)
1. Create your `.env` file by copying `.env.example`:
   ```powershell
   # Windows PowerShell:
   copy .env.example .env

   # Mac/Linux:
   cp .env.example .env
   ```
2. Open the newly created `.env` file in VS Code or Notepad and set your API key:
   ```ini
   FHIR_BASE_URL=http://localhost:8080/fhir
   GEMINI_API_KEY=AIzaSyYourActualGeminiApiKeyHere
   DEFAULT_LLM_PROVIDER=gemini
   HARD_SOS_BYPASS_ENABLED=True
   ```
   *(If you are using Groq instead of Gemini, set `DEFAULT_LLM_PROVIDER=groq` and provide `GROQ_API_KEY`)*.

---

### Step 5: Start the FHIR Server via Docker Desktop
1. **Open Docker Desktop** on your computer. Wait until the whale icon in the bottom corner turns green (Engine running).
2. Run this command in your project terminal:
   ```powershell
   docker compose up -d
   ```
   > **What this does**: Docker will automatically download the `hapiproject/hapi:latest` image and start the HAPI FHIR server in the background.
3. Wait about 20–30 seconds for the Java FHIR server to initialize.
4. **Verification**: Open your browser and go to:  
   👉 [http://localhost:8080/fhir/metadata](http://localhost:8080/fhir/metadata)  
   If it returns a large JSON document with `"resourceType": "CapabilityStatement"`, the server is running successfully!

---

### Step 6: Seed Synthetic Emergency Data
Now populate the database with emergency hospitals (e.g. Rajiv Gandhi Government General Hospital, Stanley Medical College, Chromepet GH) and synthetic trauma patients:
```powershell
python scripts/seed_synthea.py
```
**Expected terminal output**:
```text
Connecting to HAPI FHIR server at http://localhost:8080/fhir
[1/2] Seeding Emergency Hospitals / Organizations...
  + Seeded Hospital: Rajiv Gandhi Government General Hospital (RGGGH) (ID: hosp-rajiv-gandhi-gh)
  + Seeded Hospital: Government Stanley Medical College Hospital (ID: hosp-stanley-medical)
  + Seeded Hospital: Government Hospital Chromepet (ID: hosp-chromepet-gh)

[2/2] Seeding Synthea Synthetic Patient Records...
  + Seeded Patient: Karthik Subramanian | ABHA: 91-4589-2314-7856
  + Seeded Patient: Ananya Venkatesh | ABHA: 91-8890-5621-3412
  + Seeded Patient: Mohammed Imran | ABHA: 91-1234-9876-4321
  + Seeded Patient: Priya Rajesh | ABHA: 91-7744-1122-9900

Seeding complete! Verifying patient search...
  Total Patients currently in HAPI FHIR store: 4
HAPI FHIR server seeded successfully with Synthea patients & hospitals!
```

---

### Step 7: Launch the Web Dashboard
Start the emergency dispatcher dashboard server:
```powershell
python -m uvicorn src.dashboard.server:app --port 8000 --reload
```
Open your browser and visit:
👉 **[http://localhost:8000](http://localhost:8000)**

In the dashboard:
1. Verify the top status pill says **HAPI FHIR R4: Online (Port 8080)**.
2. Click **"Simulate Incident"** at top right.
3. Pick a preset incident (e.g., **Tambaram Flyover Polytrauma**) and click **"Dispatch Incident"**.
4. Watch the real-time AI triage, hospital bed reservation, and automated FHIR pre-registration happen!

---

## 🧪 Optional: Running Tests & CLI Demo

### Run Full Test Suite
To verify that all 31 unit tests, safety guardrails, and FHIR integrations pass:
```powershell
python -m pytest tests/ -v
```

### Run Command-Line Simulation Demo
To run an emergency dispatch test purely inside the terminal without the browser:
```powershell
python scripts/run_demo.py
```

---

## ⚠️ Troubleshooting & FAQ

#### 1. Error: `failed to connect to the docker API at npipe`
- **Cause**: Docker Desktop is closed or its engine has not finished starting.
- **Fix**: Open Docker Desktop from your Start Menu, wait until it says "Engine running", then re-run `docker compose up -d`.

#### 2. Error: `HAPI FHIR server is not answering /metadata`
- **Cause**: The container was just started and is still booting up (it takes ~15-20 seconds for the Java Spring Boot service to start).
- **Fix**: Wait 20 seconds, verify [http://localhost:8080/fhir/metadata](http://localhost:8080/fhir/metadata) loads in your browser, and re-run your command.

#### 3. Why was `# data/hapi_data/` in `.gitignore`?
- **Explanation**: It was an unused entry from an initial configuration template. Docker stores HAPI FHIR data inside the virtual container directly, so no folder on your host hard drive is used or needed.
