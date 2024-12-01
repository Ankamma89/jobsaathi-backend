import re
from langchain.llms import OpenAI
# from langchain_community.llms import OpenAI
# from langchain import LLMChain, PromptTemplate
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from db import resume_details_collection,profile_details_collection, onboarding_details_collection,user_details_collection
import os
import json
from firebase import Firebase
from PyPDF2 import PdfReader 
import math
from jsontemplates import proffessional, creative,templates

firebaseConfig = {
  "apiKey": os.environ.get("FIREBASE_APIKEY"),
  "authDomain": os.environ.get("FIREBASE_AUTHDOMAIN"),
  "databaseURL": os.environ.get("FIREBASE_DATABASEURL"),
  "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
  "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
  "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
  "appId": os.environ.get("FIREBASE_APP_ID"),
  "measurementId": os.environ.get("FIREBASE_MEASUREMENT_ID")
  }


firebase = Firebase(firebaseConfig)
storage = firebase.storage()

OPENAIKEY=os.environ['OPENAIKEY']


llm = OpenAI(openai_api_key=OPENAIKEY, model_name="gpt-3.5-turbo-instruct",  max_tokens=-1)

# llm = OpenAI(openai_api_key=OPENAIKEY,  max_tokens=-1)

#template = """You are a chatbot who helps people to build their resume/portfolio. This is the html and css of the portfolio {html}.This is basic info {profile} to begin.Analyze the Html properly.The following statement "{statement}" would be an instruction or information related to introduction,skills, achievements, education, projects or any other section in the resume. Analyze the statement and update the Html and css code according to statement. You are free to add or remove a section as per the scenario. Make the resume attractive in styling. Keep the sections of the resume one after another in vertical format or two column vertical format. Return me only the html and css.fonts,colors,css and html should be same as initial html and css
#"""

template = """
You are a chatbot who helps people build their resumes/portfolios. Below are the inputs:
- JSON Template: {json}
- Profile: {profile}
- Instruction: "{statement}"

1. **Only** return the updated JSON in valid JSON format.
2. **Do not** include any additional text, labels, or explanations (e.g., "JSON Template:").
3. Ensure that the JSON is well-formatted and properly closed.

Analyze the instruction and update only the relevant sections in the JSON template based on the profile and statement. Return **only** the updated JSON template in a valid and clean JSON file format. Do not include any extra text or explanation.Add more content for about and job details.Return json only.
"""


skills_analyze_template = """You are a chatbot who helps people to build their resume/portfolio. This is the text of the portfolio {html}. Analyze the text properly and find all the skills of the person from the resume and return me only the skills of the candidate in comma seperated formated.
Return the skills as a **comma-separated list**, without including any extra information, explanations, or context. Example format: "Skill1, Skill2, Skill3".
"""
prompt = PromptTemplate(template=template, input_variables=["json", "statement","profile"])
llm_chain = LLMChain(prompt=prompt, llm=llm)

skills_analyze_prompt = PromptTemplate(template=skills_analyze_template, input_variables=["html"])
skills_analyze_llm_chain = LLMChain(prompt=skills_analyze_prompt, llm=llm)

#template_path = os.path.join(os.path.dirname(__file__), 'templates/resumes', 'testtemp.html')
#file=open(template_path, 'r', encoding='utf-8').read()

def query_update_billbot(user_id, statement, build_status):
    resume_html,json_template = get_resume_html_db(user_id)
    user=user_details_collection.find_one({"user_id":user_id})
    profile=profile_details_collection.find_one({"user_id":user_id},{"_id":0})
    #resume_html="\n\n\n<style>/* Fonts */ /* Family */ h1 { font-family: 'Julius Sans One', sans-serif; } h2 { /* Contact, Skills, Education, About me, Work Experience */ font-family: 'Archivo Narrow', sans-serif; } h3 { /* Accountant */ font-family: 'Open Sans', sans-serif; } .jobPosition span, .projectName span { font-family: 'Source Sans Pro', sans-serif; } .upperCase { text-transform: uppercase; } .smallText, .smallText span, .smallText p, .smallText a { font-family: 'Source Sans Pro', sans-serif; text-align: justify; } /* End Family */ /* Colors */ h1 { color: #111; } .leftPanel, .leftPanel a { color: #bebebe; text-decoration: none; } .leftPanel h2 { color: white; } /* End Colors */ /* Sizes */ h1 { font-weight: 300; font-size: 1.2cm; transform:scale(1,1.15); margin-bottom: 0.2cm; margin-top: 0.2cm; text-transform: uppercase; } h2 { margin-top: 0.1cm; margin-bottom: 0.1cm; } .leftPanel, .leftPanel a { font-size: 0.38cm; } .projectName span, .jobPosition span { font-size: 0.35cm; } .smallText, .smallText span, .smallText p, .smallText a { font-size: 0.35cm; } .leftPanel .smallText, .leftPanel .smallText, .leftPanel .smallText span, .leftPanel .smallText p, .smallText a { font-size: 0.45cm; } .contactIcon { width: 0.5cm; text-align: center; } p { margin-top: 0.05cm; margin-bottom: 0.05cm; } /* End Sizes */ .bolded { font-weight: bold; } .white { color: white; } /* End Fonts */ /* Layout */ body { background: rgb(204,204,204); width: 21cm; height: 29.7cm; margin: 0 auto; } /* Printing */ page { background: white; display: block; margin: 0 auto; margin-bottom: 0.5cm; } page[size='A4'] { width: 21cm; height: 29.7cm; } @page { size: 21cm 29.7cm; padding: 0; margin: 0mm; border: none; border-collapse: collapse; } /* End Printing */ .container { display: flex; flex-direction: row; width: 100%; height: 100%; } .leftPanel { width: 27%; background-color: #484444; padding: 0.7cm; display: flex; flex-direction: column; align-items: center; } .rightPanel { width: 73%; padding: 0.7cm; } .leftPanel img { width: 4cm; height: 4cm; margin-bottom: 0.7cm; border-radius: 50%; border: 0.15cm solid white; object-fit: cover; object-position: 50% 50%; } .leftPanel .details { width: 100%; display: flex; flex-direction: column; } .skill { display: flex; flex-direction: row; justify-content: space-between; } .bottomLineSeparator { border-bottom: 0.05cm solid white; } .yearsOfExperience { width: 1.6cm; display: flex; flex-direction: row; justify-content: center; } .alignleft { text-align: left !important; width: 1cm; } .alignright { text-align: right !important; width: 0.6cm; margin-right: 0.1cm } .workExperience>ul { list-style-type: none; padding-left: 0; } .workExperience>ul>li { position: relative; margin: 0; padding-bottom: 0.5cm; padding-left: 0.5cm; } .workExperience>ul>li:before { background-color: #b8abab; width: 0.05cm; content: ''; position: absolute; top: 0.1cm; bottom: -0.2cm; /* change this after border removal */ left: 0.05cm; } .workExperience>ul>li::after { content: ''; position: absolute; background-image: url('data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' aria-hidden='true' viewBox='0 0 32 32' focusable='false'%3E%3Ccircle stroke='none' fill='%23484444' cx='16' cy='16' r='10'%3E%3C/circle%3E%3C/svg%3E'); background-repeat: no-repeat; background-size: contain; left: -0.09cm; top: 0; width: 0.35cm; height: 0.35cm; } .jobPosition { display: flex; flex-direction: row; justify-content: space-between; } .item { padding-bottom: 0.7cm; padding-top: 0.7cm; } .item h2{ margin-top: 0; } .lastParagrafNoMarginBottom { margin-bottom: 0; } .workExperience>ul>li ul { padding-left: 0.5cm; list-style-type: disc; } /*End Layout*/</style>"
    #html_code = llm_chain.run({"html": str(file),"section":build_status, "statement": {build_status:statement},"profile":profile}) 
    temp=templates.get(json_template,proffessional)
    print(temp,'json_template')
    json = llm_chain.run({"json": str(temp),"statement": {build_status:statement},"profile":profile}) 
    return json

def get_resume_html_db(user_id):
    if resume_data := resume_details_collection.find_one({"user_id": user_id}):
        resume_html = resume_data.get("resume_html")
        json_template=resume_data.get("json_template")
        return str(resume_html),str(json_template)
    else:
        return ""

def add_html_to_db(user_id, json):
    print(json,'json')
    resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_json": json}})

def add_realhtml_to_db(user_id, html):
    print(html,'html')
    resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_html": html}})

def analyze_resume(user_id, text=False):
    if not text:
        if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
            resume_html = resume_details.get("resume_html")
            skills = skills_analyze_llm_chain.run(resume_html)
            print(skills)
            skills = skills.strip()
            resume_details_collection.update_one({"user_id": user_id},{"$set": {"skills": skills}})
            return 
        else:
            return
    else:
        print(text,'text')
        skills = skills_analyze_llm_chain.run(text) 
        print(skills)
        skills = skills.strip()
        resume_details_collection.update_one({"user_id": user_id},{"$set": {"skills": skills}})
        return 

def extract_text_pdf(path):
    reader = PdfReader(path) 
    print(len(reader.pages)) 
    page = reader.pages[0] 
    text = page.extract_text() 
    return text 

def upload_file_firebase(obj, path):
    storage.child(path).put(obj)
    link = storage.child(path).get_url(None)
    print(link,'link')
    return link

resume_question_template = """I have asked a person whether he/she has a portfolio/resume or not.{statement} is the person's reponse. Analyse the statement and return me 'yes' if he has a resume and 'no' if he doesn't have one and if the response is something weird like not a clear cut yes or no return me 'weird'
"""

resume_question_prompt = PromptTemplate(template=resume_question_template, input_variables=["statement"])
resume_question_llm_chain = LLMChain(prompt=resume_question_prompt, llm=llm)


def query__billbot(statement):
    resp = resume_question_llm_chain.run(statement) 
    return str(resp).strip().lower()


def outbound_messages(build_status):
    messages = []
    if build_status == "introduction":
         messages = [{"user":"billbot","msg": "Hi, The right side of your screen will display your resume. You can give me instruction to build it in the chat."},{"user":"billbot","msg": "Provide a small introduction about you?"}]
    elif build_status == "contactinfo":
         messages = [{"user":"billbot","msg": "Can you provide your contact info like phone number, mail id etc.?"}]
    elif build_status == "education":
         messages = [{"user":"billbot","msg": "Tell me about your schooling and higher education?"}]
    elif build_status == "experiences":
         messages = [{"user":"billbot","msg": "Tell me about your current employment and past experiences (if any)?"}]
    elif build_status == "skills":
         messages = [{"user":"billbot","msg": "Tell me your skill list?"}]
    elif build_status == "projects":
         messages = [{"user":"billbot","msg": "Tell me about your projects?"}]
    else:
         messages = [{"user":"billbot","msg": "You can go ahead and tell me to do anything!"}]
    return messages
    

def next_build_status(build_status):
    status={
        "introduction": "contactinfo",
        "contactinfo": "education",
        "education": "experiences",
        "experiences": "skills",
        "skills": "projects",
        "projects": "endofchecklist",
        "endofchecklist": "endofchecklist"
        }
    return status.get(build_status)

def updated_build_status(user_id, nxt_build_status):
    onboarding_details_collection.update_one({"user_id": user_id},{"$set": {"build_status": nxt_build_status}})
    return 




def text_to_html(text):
  # Regular expression to match URLs, including optional http/https
  url_regex = r"(http|https):\/\/(\w+\.)+\w{2,}(?:\/\S+)?/"
  # Replace URLs with anchor tags
  return re.sub(url_regex, lambda match: f'<a href="{match.group(0)}" target="_blank">{match.group(0)}</a>', text)



def calculate_total_pages(total_elements, page_size):
    return math.ceil(total_elements / page_size)

def mbsambsasmbsa():
    html_code = llm_chain.run({"html": str(""), "statement": "I AM M b sai aditya. I am a final year student at NIT Karnataka."}) 
    return html_code