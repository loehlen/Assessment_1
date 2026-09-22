# LAWS90286 - DAY 2

## ENVIRONMENT SETUP

### Step 1 - Create Virtual Environment
1. create virtual environment
> python -m venv .venv
2. make sure the .venv folder was created, then activate virtual environment
> source .venv/bin/activate


### Step 2 - Install Dependencies / Python Libraries
1. create a requirements.txt file
2. add, each on a newline, openai + streamlit + python-dotenv
3. run:
> pip install -r requirements.txt

### Step 3 - Create a .env file to store our secrets (including OpenAI API Key)
1. create .env file
> touch .env
2. add the OPENAI_API_KEY to the .env file

## CREATE STREAMLIT APPLICATION
1. create python file entrypoint
> touch home.py
2. run streamlit web server
> streamlit run home.py


## NOTE - COMMIT CHANGES
1. Open source control on LHS of screen
2. Click the plus signs (+) to "stage" your changes
3. Add a commit message in the message bar
4. Click "commit"
5. Click "sync changes"
6. IMPORTANT! check your GitHub repository to confirm this worked