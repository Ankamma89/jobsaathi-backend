from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
from json import dumps
from flask import Flask, json, request, render_template, redirect, abort, session, flash, make_response
from client_secret import client_secret, initial_html
from db import task_seen_by_collection, tasks_details_collection,user_details_collection, onboarding_details_collection, jobs_details_collection, candidate_job_application_collection,candidate_task_proposal_collection, chatbot_collection, resume_details_collection, profile_details_collection, saved_jobs_collection,task_chat_details_collection, chat_details_collection, connection_details_collection, connection_task_details_collection,plans_collection,notification_collection
from helpers import  query_update_billbot,get_resume_html_db, add_html_to_db,add_realhtml_to_db, analyze_resume, upload_file_firebase, extract_text_pdf, outbound_messages, next_build_status, updated_build_status, text_to_html, calculate_total_pages, mbsambsasmbsa
from jitsi import create_jwt
import os
from flask import jsonify
import jwt
from datetime import datetime,timedelta
from bson import ObjectId
import json
from flask.json import JSONEncoder
import requests
import pathlib
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import uuid
import time
import pusher
from flask_cors import CORS
from collections import Counter
import re
import razorpay


# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(os.environ["RAZORPAY_ID"], os.environ["RAZORPAY_KEY"]))

  # Load environment variables from .env file


pusher_client = pusher.Pusher(
  app_id=os.environ['PUSHER_APP_ID'],
  key=os.environ['PUSHER_KEY'],
  secret=os.environ['PUSHER_SECRET'],
  cluster=os.environ['PUSHER_CLUSTER'],
  ssl=True
)

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)



app = Flask(__name__)
# Enable CORS for the entire app
CORS(app)
app.secret_key = os.environ['APP_SECRET']

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
app.json_encoder = CustomJSONEncoder


url_ = os.environ['APP_URL']
APP_SECRET = os.environ['APP_SECRET']

GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_config(
    client_config=client_secret,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri=f"{url_}/callback"
)

def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return redirect("/") 
        else:
            return function(*args, **kwargs)
    return wrapper

def extract_bearer_token(request):
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None

def get_user(token):
    user_id = jwt.decode(token, APP_SECRET,algorithms=['HS256']).get('public_id')
    if user_id is None:
        return redirect("/") 
    else:
        current_user = user_details_collection.find_one({"user_id": user_id},{"_id": 0,'password':0})
        return current_user

def newlogin_is_required(function):
    def wrapper(*args, **kwargs):
        token=extract_bearer_token(request)
        user=get_user(token)
        if user is None:
            return redirect("/") 
        else:
             return function(user,*args, **kwargs)
    return wrapper

def is_candidate(function):
    def wrapper(*args, **kwargs):
        token = extract_bearer_token(request)
        user = get_user(token)
        if user is None:
            return abort(500)  
        else:
            purpose = user.get('role')
            if purpose == "jobseeker":
                return function(*args, **kwargs)
            else:
                abort(500, {"message": "You are not a candidate."})
    return wrapper
def is_hirer(function):
    def wrapper(*args, **kwargs):
        token=extract_bearer_token(request)
        user = get_user(token)
        if user is None:
            return abort(500)   
        else:
            purpose = user.get('role')
            if purpose == "hirer":
                return function(*args, **kwargs)
            else:
                abort(500, {"message":{"You are not a Hirer."}})
    return wrapper

def is_onboarded(function):
    def wrapper(*args, **kwargs):
        token=extract_bearer_token(request)
        user = get_user(token)
        if user is None:
            return abort(500)  
        onboarded = user.get("onboarded")
        if onboarded:
            return function(*args, **kwargs)
        else:
             return jsonify({"message":"onboarded"}),200
    return wrapper


@app.route("/about-us", methods = ['GET'])
def about_us():
    user_logged_in = False
    if session.get('google_id') is not None:
        user_logged_in = True
    user_name = session.get("name")
    resp = make_response(render_template("about_us.html", user_name=user_name, user_logged_in=user_logged_in))
    return resp

@app.route("/contact-us", methods = ['GET'])
def contact_us():
    user_logged_in = False
    if session.get('google_id') is not None:
        user_logged_in = True
    user_name = session.get("name")
    resp = make_response(render_template("contact_us.html", user_name=user_name, user_logged_in=user_logged_in))
    return resp

@app.route("/life", methods = ['GET'])
def starte():
        return render_template("signup.html")
    
@app.route("/", methods = ['GET'])
def start():
    if session.get('token') is None:
        user_name = session.get("name")
        resp = jsonify({"message":"success"}),200
        return resp
    else:
        return redirect("/dashboard")
    
@app.route("/searchJobs",methods = ['GET'])   
def search_jobs(user):
    searched_for = request.args.get("search")
    logged_in = True
    if user.get('user_id') is None:
        logged_in = False
    if logged_in:
        return redirect("/dashboard")
    # pipeline = [
    #     {
    #         '$lookup': {
    #             'from': 'jobs_details', 
    #             'localField': 'job_id', 
    #             'foreignField': 'job_id', 
    #             'as': 'job_details'
    #         }
    #     }, 
    #     {
    #         '$project': {
    #             '_id': 0,
    #             'job_details._id': 0
    #         }
    #     }
    # ]
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"job_title": {"$regex": searched_for, "$options": "i"}},
                    {"job_description": {"$regex": searched_for, "$options": "i"}},
                    {"job_type": {"$regex": searched_for, "$options": "i"}},
                    {"job_topics": {"$regex": searched_for, "$options": "i"}}
                ]
            }
        },
         {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        }
    ]
    
    all_jobs = list(jobs_details_collection.aggregate(pipeline))
    return jsonify({'all_jobs':all_jobs, 'logged_in':logged_in})

@app.route("/signup", methods = ['GET'])
def signup():
    if session.get('google_id') is None:
        return render_template("index.html")
    else:
        return redirect("/dashboard")

@app.route("/alljobs", methods = ['GET'], endpoint='alljobs')
@is_candidate
@newlogin_is_required
def alljobs(user):
    user_name = user.get("user_id")
    onboarded = user.get("onboarded")
    user_id = user.get("user_id")
    if onboarded == False:
        return redirect("/onboarding")
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    resume_built = onboarding_details.get("resume_built")
    if not resume_built: 
        return redirect("/billbot")
    pageno = request.args.get("pageno")
    page_number = 1  # The page number you want to retrieve
    if pageno is not None:
        page_number = int(pageno)
    page_size = 7   # Number of documents per page
    total_elements = len(list(jobs_details_collection.find({},{"_id": 0})))
    total_pages = calculate_total_pages(total_elements, page_size)
    skip = (page_number - 1) * page_size
    pipeline = [
        {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
        {
                '$lookup': {
                    'from': 'saved_jobs', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'saved_jobs_details'
                }
            }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
    ]
    all_jobs = list(jobs_details_collection.aggregate(pipeline))
    # return all_applied_jobs
    return jsonify(user_name=user_name, onboarding_details=onboarding_details, all_jobs=all_jobs, total_pages=total_pages,page_number=page_number)


@app.route("/dashboard", methods=['GET'], endpoint='dashboard')
@newlogin_is_required
def dashboard(user):
    user_name = user.get("name")
    onboarded = user.get("onboarded")
    user_id = user.get("user_id")
    if not onboarded:
        return jsonify({"message": "please onboard"}), 200
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id}, {"_id": 0})
    purpose = user.get("role")
    resume_built = onboarding_details.get("resume_built")

    if purpose == 'hirer':
        return handle_hirer_dashboard(user_id, user_name, onboarding_details)
    else:
        return handle_jobseeker_dashboard(user_id, user_name, onboarding_details, resume_built)

def handle_hirer_dashboard(user_id, user_name, onboarding_details):
    approved_by_admin = onboarding_details.get('approved_by_admin')
    if not approved_by_admin:
        return jsonify({"message": "admin approval needed"}), 200
    print('stats')
    pipeline = [
            {
                "$match": {"user_id": user_id}
            },
            {
                '$lookup': {
                    'from': 'candidate_job_application', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'applicants'
                }
            },
            {
            '$addFields': {
                'applicants_count': {'$size': '$applicants'},
            }
           },
           {'$sort':{'created_on':-1}},
           {  
        '$project': {
            '_id': 0, 
            'applicants._id':0,
            #'applicants_count': 1,
            #'applicants': 1

        },
    }
        # Skip documents based on the calculated skip value  # Limit the number of documents per page
        ]
    all_jobs_wapplicants = list(jobs_details_collection.aggregate(pipeline))
    all_tasks = list(tasks_details_collection.find({"user_id": user_id}, {"_id": 0}))
    
    all_published_jobs = list(jobs_details_collection.find({"user_id": user_id, "status": "published"}, {"_id": 0}))
    total_selected_candidates = list(candidate_job_application_collection.find({"hirer_id": user_id, "status": "Accepted"}, {"_id": 0}))
    applicants=list(candidate_job_application_collection.find({"hirer_id": user_id}, {"_id": 0}))
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    applicants_today=list(candidate_job_application_collection.find({"hirer_id": user_id,
            "applied_on": {
                "$gte": today_start, 
                "$lt": tomorrow_start
            }}, {'_id': 0}))
    stats = {
        "total_jobs": jobs_details_collection.count_documents({"user_id": user_id}),
        "total_published_jobs": len(all_published_jobs),
        "total_selected_candidates": len(total_selected_candidates),
        "applicants":len(applicants),
        "applicants_today":len(applicants_today)
    }
    return jsonify({
        "user_name": user_name,
        "onboarding_details": onboarding_details,
        "all_jobs":all_jobs_wapplicants,
        "all_tasks": all_tasks,
        "stats": stats
    })

def handle_jobseeker_dashboard(user_id, user_name, onboarding_details, resume_built):
    #if not resume_built:
    #   return jsonify({"message": "please build your resume"}), 200

    resume_skills = get_resume_skills(user_id)
    regex_pattern = create_skills_regex_pattern(resume_skills)

    pageno = request.args.get("page", 1, type=int)
    page_size = 7

    # Fetch all jobs matching the user's skills
    all_jobs = ''

    # Fetch all tasks
    all_tasks = ''

    # Fetch saved jobs
    saved_jobs = list(saved_jobs_collection.find({"user_id": user_id}, {"_id": 0}))
    
    # Fetch applied jobs
    pipeline = [
            {
                "$match": {"user_id": user_id}
            },
            {
                '$lookup': {
                    'from': 'jobs_details', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'job_details'
                }
            },{
            '$lookup': {
                'from': 'profile_details', 
                'localField': 'job_details.user_id', 
                'foreignField': 'user_id', 
                'as': 'company_details'
            }
        }, 
           {
        '$project': {
            '_id': 0, 
            'job_details._id':0
        },
    },
    {"$sort":{"updated_at":-1}},
        ]
    taskpipeline = [
            {
                "$match": {"user_id": user_id}
            },
            {
                '$lookup': {
                    'from': 'tasks_details', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'task_details'
                }
            },
           {
        '$project': {
            '_id': 0, 
            'task_details._id':0
        },
    },
    {"$sort":{"updated_at":-1}},
        ]
    applied_jobs = list(candidate_job_application_collection.aggregate(pipeline))
    #applied_jobs = list(candidate_job_application_collection.find({"user_id": user_id}, {"_id": 0}))
    
    # Fetch task proposals
    task_proposals = list(candidate_task_proposal_collection.aggregate(taskpipeline))
    
    # Fetch connections
    connections = list(connection_details_collection.find({"user_id": user_id}, {"_id": 0}))

    profile_details = profile_details_collection.find_one({"user_id": user_id}, {"_id": 0})


    return jsonify({
        "user_name": user_name,
        "onboarding_details": onboarding_details,
        "all_jobs": all_jobs,
        "all_tasks": all_tasks,
        "saved_jobs": saved_jobs,
        "applied_jobs": applied_jobs,
        "task_proposals": task_proposals,
        "connections": connections,
        "profile_details": profile_details,
        "total_pages": 3,
        "page_number": pageno
    })

def get_resume_skills(user_id):
    resume = resume_details_collection.find_one({'user_id': user_id}, {'skills': 1})
    if resume and 'skills' in resume:
        skills_string = resume['skills']
        return [skill.strip().lower() for skill in skills_string.split(',') if skill.strip()]
    return []

def create_skills_regex_pattern(resume_skills):
    if not resume_skills:
        return '.*'  # Match everything if no skills are found
    regex_patterns = ['|'.join(skill.split()) for skill in resume_skills]
    return '|'.join(regex_patterns)

def calculate_total_pages(total_elements, page_size):
    return max(1, (total_elements + page_size - 1) // page_size)


@app.route("/job_support", methods = ['GET'], endpoint='job_support')
@newlogin_is_required
def job_support(user):
    user_name = user.get("name")
    onboarded = user.get("onboarded")
    user_id = user.get("user_id")
    if onboarded == False:
         return jsonify({"message":"please onboard"}),200
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    purpose = onboarding_details.get("purpose")
    resume_built = onboarding_details.get("resume_built")
    if purpose == 'hirer':
        approved_by_admin = onboarding_details.get('approved_by_admin')
        if approved_by_admin:
            pageno = request.args.get("pageno")
            page_number = 1  # The page number you want to retrieve
            if pageno is not None:
                page_number = int(pageno)
            page_size = 7   # Number of documents per page
            total_elements = len(list(jobs_details_collection.find({"user_id": user_id},{"_id": 0})))
            total_pages = calculate_total_pages(total_elements, page_size)
            skip = (page_number - 1) * page_size
            pipeline = [
                   {'$match': {"user_id": user_id} },
                    {
                        '$project': {
                            '_id': 0,
                        }
                    },
                    {"$skip": skip},  # Skip documents based on the calculated skip value
                    {"$limit": page_size}  # Limit the number of documents per page
                ]
            all_tasks = list(tasks_details_collection.aggregate(pipeline))
            all_published_tasks = list(jobs_details_collection.find({"user_id": user_id, "status":"published"},{"_id": 0}))
            total_selected_candidates = list(candidate_job_application_collection.find({"hirer_id": user_id, "status":"Accepted"},{"_id": 0}))
            stats = {
                "total_tasks" : len(all_tasks),
                "total_published_tasks" : len(all_published_tasks),
                "total_selected_candidates" : len(total_selected_candidates)
            }
            return jsonify({
            "user_name": user_name,
            "onboarding_details": onboarding_details,
            "all_tasks": all_tasks,
            "stats": stats,
            "total_pages": total_pages,
            "page_number": page_number
        })
        else:
            return jsonify({"message":"approval by admin is pending"}),200
    else:
        if not resume_built: 
             return jsonify({"message":"please build resume"}),200
        resume_skills_string = resume_details_collection.find_one({'user_id': user_id}, {'skills': 1}).get("skills")
        resume_skills = [skill.strip().lower() for skill in resume_skills_string.split(',')]
        regex_patterns = []
        for skill in resume_skills:
            skill_words = skill.split()
            skill_pattern = '|'.join(skill_words)
            regex_patterns.append(skill_pattern)
        regex_pattern = '|'.join(regex_patterns)
        length_pipeline = [
                 {
        '$match': {
            'status': 'published',
               '$or': [
                {'task_title': {'$regex': regex_pattern, '$options': 'i'}},
                {'task_description': {'$regex': regex_pattern, '$options': 'i'}},
                {'task_topics': {'$regex': regex_pattern, '$options': 'i'}},
            ]
        }
    }, 
            {
                '$project': {
                    '_id': 0
                }
            }
        ]

        pageno = request.args.get("pageno")
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(tasks_details_collection.aggregate(length_pipeline)))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
                 {
        '$match': {
            'status': 'published',
               '$or': [
                {'task_title': {'$regex': regex_pattern, '$options': 'i'}},
                {'task_description': {'$regex': regex_pattern, '$options': 'i'}},
                {'task_topics': {'$regex': regex_pattern, '$options': 'i'}},
            ]  # You may add other conditions to filter jobs if needed
        }
    },
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            }, 
            {
                '$project': {
                    '_id': 0
                }
            },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
        ]

        all_tasks = list(tasks_details_collection.aggregate(pipeline))
        all_updated_jobs = []
        for idx, task in enumerate(all_tasks):
            if applied := candidate_task_proposal_collection.find_one({"task_id": task.get("task_id"),"user_id":  user_id},{"_id": 0}):
                pass
            else:
                all_updated_jobs.append(task)
        profile_details = profile_details_collection.find_one({"user_id": user_id},{"_id": 0})
        return jsonify({"user_name":user_name, "onboarding_details":onboarding_details, "all_jobs":all_updated_jobs,"all_tasks":all_tasks, "profile_details":profile_details, "total_pages":total_pages, "page_number":page_number})
    
@app.route("/applied_jobs", methods = ['GET'], endpoint='applied_jobs')
@newlogin_is_required
@is_candidate
def applied_jobs(user):
    user_name = user.get("name")
    onboarded = user.get("onboarded")
    user_id = user.get("user_id")
    if onboarded == False:
         return jsonify({"message":"user is not onboarded"}),400
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    resume_built = onboarding_details.get("resume_built")
    if not resume_built: 
         return jsonify({"message":"please build resume"}),400
    pageno = request.args.get("pageno")
    page_number = 1  # The page number you want to retrieve
    if pageno is not None:
        page_number = int(pageno)
    page_size = 7   # Number of documents per page
    length_pipeline = [
                {"$match": {"user_id": user_id}},
        {
            '$project': {
                '_id': 0
            }
        }
    ]
    total_elements = len(list(candidate_job_application_collection.aggregate(length_pipeline)))
    total_pages = calculate_total_pages(total_elements, page_size)
    skip = (page_number - 1) * page_size
    pipeline = [
                {"$match": {"user_id": user_id}},
        {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
        {
            '$lookup': {
                'from': 'onboarding_details', 
                'localField': 'job_details.user_id', 
                'foreignField': 'user_id', 
                'as': 'user_details'
            }
        }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0,
                'user_details._id': 0
            }
        },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
    ]
    all_applied_jobs = list(candidate_job_application_collection.aggregate(pipeline))
    # return all_applied_jobs
    return jsonify({'user_name':user_name, 'onboarding_details':onboarding_details, 'all_applied_jobs':all_applied_jobs, 'total_pages':total_pages, 'page_number':page_number})

@app.route("/saved_jobs", methods = ['GET', 'POST'], endpoint='saved_jobs')
@newlogin_is_required
@is_candidate
def saved_jobs(user):
    user_name = user.get("user_id")
    onboarded = user.get("onboarded")
    user_id = user.get("user_id")
    if onboarded == False:
         return jsonify({"message":"please onboard"}),400
    if request.method == 'POST':
        pass
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    resume_built = onboarding_details.get("resume_built")
    if not resume_built: 
         return jsonify({"message":"resume is not built"}),400
    pageno = request.args.get("pageno")
    page_number = 1  # The page number you want to retrieve
    if pageno is not None:
        page_number = int(pageno)
    page_size = 7   # Number of documents per page
    length_pipeline = [
                    {"$match": {"user_id": user_id}},
            {
                '$project': {
                    '_id': 0
                }
            }
        ]
    total_elements = len(list(saved_jobs_collection.aggregate(length_pipeline)))
    total_pages = calculate_total_pages(total_elements, page_size)
    skip = (page_number - 1) * page_size
    pipeline = [
                    {"$match": {"user_id": user_id}},
            {
                '$lookup': {
                    'from': 'jobs_details', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'job_details'
                }
            }, 
                    {
            '$lookup': {
                'from': 'onboarding_details', 
                'localField': 'job_details.user_id', 
                'foreignField': 'user_id', 
                'as': 'user_details'
            }
        }, 
            {
                '$project': {
                    '_id': 0,
                    'job_details._id': 0,
                    'user_details._id': 0
                }
            },
            {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
        ]
    all_saved_jobs = list(saved_jobs_collection.aggregate(pipeline))
    # return all_applied_jobs
    return jsonify({'user_name':user_name, 'onboarding_details':onboarding_details, 'all_saved_jobs':all_saved_jobs,'total_pages':total_pages, 'page_number':page_number})


@app.route("/profile", methods=['GET', 'POST'], endpoint='profile_update')
@newlogin_is_required
@is_candidate
def profile_update(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    if request.method == 'POST':
        profile_data = dict(request.form)
        if 'description' in profile_data:
            profile_data['description'] = profile_data['description'].strip()
        if 'profile_pic' in request.files and str(request.files['profile_pic'].filename)!="":
            profile_pic = request.files['profile_pic']
            profile_pic_link = upload_file_firebase(profile_pic, f"{user_id}/profile_pic.png")
            profile_data['profile_pic'] = profile_pic_link
        profile_details_collection.update_one({"user_id": user_id},{"$set": profile_data})
        return jsonify({"message":"profile updated successfully"}),200
    if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        if purpose == 'jobseeker':
            return jsonify({ 'profile_details':profile_details, 'user_id':user_id}) 
        elif purpose == 'hirer':
            return jsonify({'profile_details':profile_details})
        else:
            abort(500, {"message" : "candidate or hirer not found in the records."})
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})

@app.route("/profile-update", methods=['GET', 'POST'], endpoint='profile_update_info')
@newlogin_is_required
def profile_update_info(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    user=user_details_collection.find_one({"user_id":user_id},{"_id":0,"password":0})
    if request.method == 'POST':
        form_data = dict(request.form) 
        print(form_data,'formdata')
        profile_photo=user.get("profile_photo")
        if 'profile_pic' in request.files and str(request.files['profile_pic'].filename)!="":
            profile_pic = request.files['profile_pic']
            profile_photo=upload_file_firebase(profile_pic,f'{user_id}/profile_pic.png')
        name= form_data.get("name")
        email= form_data.get("email")
        user_details_collection.update_one({"user_id": user_id},{"$set": {"email":email,"name":name,"profile_photo":profile_photo}})
        profile_details_collection.update_one({"user_id": user_id},{"$set": {"name":name,"email":email}})
        return jsonify({"message":"profile updated successfully"}),200
    if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        if purpose == 'jobseeker':
            return jsonify({ 'profile_details':profile_details, 'user_id':user_id}) 
        elif purpose == 'hirer':
            return jsonify({'profile_details':profile_details})
        else:
            abort(500, {"message" : "candidate or hirer not found in the records."})
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})

@app.route("/profile-sections-update", methods=['GET', 'POST'], endpoint='profile_sections_update')
@newlogin_is_required
def profile_sections_update(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    user=user_details_collection.find_one({"user_id":user_id},{"_id":0,"password":0})
    if request.method == 'POST':
        form_data = dict(request.form) 
        print(form_data,'formdata')
        profile_photo=user.get("profile_photo")
        if 'profile_pic' in request.files and str(request.files['profile_pic'].filename)!="":
            profile_pic = request.files['profile_pic']
            profile_photo=upload_file_firebase(profile_pic,f'{user_id}/profile_pic.png')
        introduction= form_data.get("introduction")
        education= form_data.get("education")
        experience= form_data.get("experience")
        skills= form_data.get("skills")
        #user_details_collection.update_one({"user_id": user_id},{"$set": {"email":email,"name":name,"profile_photo":profile_photo}})
        profile_details_collection.update_one({"user_id": user_id},{"$set": {"introduction":introduction,"education":education,"experience":experience,"skills":skills}})
        return jsonify({"message":"profile updated successfully"}),200
    if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        if purpose == 'jobseeker':
            return jsonify({ 'profile_details':profile_details, 'user_id':user_id}) 
        elif purpose == 'hirer':
            return jsonify({'profile_details':profile_details})
        else:
            abort(500, {"message" : "candidate or hirer not found in the records."})
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})

@app.route("/company-sections-update", methods=['GET', 'POST'], endpoint='company_sections_update')
@newlogin_is_required
def company_sections_update(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    user=user_details_collection.find_one({"user_id":user_id},{"_id":0,"password":0})
    if request.method == 'POST':
        form_data = dict(request.form) 
        print(form_data,'formdata')
        onboard=onboarding_details_collection.find_one({"user_id":user_id})
        company_logo=onboard.get("company_logo")
        print(request.files,'file check')
        if 'company_logo' in request.files and str(request.files['company_logo'].filename)!="":
            print(request.files,'companeey logo')
            profile_pic = request.files['company_logo']
            company_logo=upload_file_firebase(profile_pic,f'{user_id}/profile_pic.png')
        companyName= form_data.get("companyName")
        location= form_data.get("location")
        industry= form_data.get("industry")
        description= form_data.get("description")
        print(company_logo,'company logo')
        #user_details_collection.update_one({"user_id": user_id},{"$set": {"email":email,"name":name,"profile_photo":profile_photo}})
        profile_details_collection.update_one({"user_id": user_id},{"$set": {"company_name":companyName,"location":location,"industry":industry,"company_logo":company_logo}})
        onboarding_details_collection.update_one({"user_id":user_id},{"$set":{"company_name":companyName,"company_description":description,"company_logo":company_logo}})
        return jsonify({"message":"profile updated successfully"}),200
    if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        if purpose == 'jobseeker':
            return jsonify({ 'profile_details':profile_details, 'user_id':user_id}) 
        elif purpose == 'hirer':
            return jsonify({'profile_details':profile_details})
        else:
            abort(500, {"message" : "candidate or hirer not found in the records."})
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})

@app.route("/profile-image", methods=['GET', 'POST'], endpoint='profile_image_info')
@newlogin_is_required
@is_candidate
def profile_image_info(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    user=user_details_collection.find_one({"user_id":user_id},{"_id":0,"password":0})
    if request.method == 'POST':
        form_data = dict(request.form)
        print(form_data,'profile')
        name= form_data.get("name")
        email= form_data.get("email")
        user_details_collection.update_one({"user_id": user_id},{"$set": {"email":email,"name":name}})
        profile_details_collection.d
        profile_details_collection.update_one({"user_id": user_id},{"$set": {"name":name,"email":email}})
        return jsonify({"message":"profile updated successfully"}),200
    if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        if purpose == 'jobseeker':
            return jsonify({ 'profile_details':profile_details, 'user_id':user_id}) 
        elif purpose == 'hirer':
            return jsonify({'profile_details':profile_details})
        else:
            abort(500, {"message" : "candidate or hirer not found in the records."})
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})

@app.route("/public/candidate/<string:user_id>", methods=['GET', 'POST'], endpoint='public_candidate_profile')
def public_candidate_profile(user_id):
    pipeline = [
            {"$match": {"user_id": user_id}},
            {
                '$lookup': {
                    'from': 'resume', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'resume_details'
                }
            }, 
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            },
                        {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'onboarding_details'
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'resume_details._id': 0,
                    'user_details._id': 0
                }
            }
        ]
    if profile_details := list(profile_details_collection.aggregate(pipeline)):
        return jsonify({'profile_details':profile_details}) 
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})


@app.route("/upload_intro_candidate", methods=['POST'], endpoint='upload_intro_candidate')
@newlogin_is_required
@is_candidate
def upload_intro_candidate(user):
    print(user,'userId')
    user_id = user.get("user_id")
    if 'intro_video' in request.files and str(request.files['intro_video'].filename)!="":
        intro_video = request.files['intro_video']
        intro_video_link = upload_file_firebase(intro_video, f"{user_id}/intro_video.mp4")
        profile_details_collection.update_one({"user_id": user_id},{"$set": {"intro_video_link": intro_video_link}})
        return jsonify({'message':'video is saved'}),200


@app.route('/login-user', methods=['GET', 'POST'], endpoint="login_user")
def login_user():
    form_data = request.get_json(force=True)
    if request.method == 'POST':
        user = user_details_collection.find_one({"email": form_data.get("email")},{"_id": 0})
        if user :
            email = form_data.get("email")
            password = form_data.get("password")
            if password==user.get("password"):
               token = jwt.encode({
               'public_id': user.get("user_id"),
               'exp' : '30000000000000000000000000'
                }, APP_SECRET)
               if user.get("role")=="jobseeker":
                  role="jobseeker"
               if user.get("role")=="hirer":
                  role="hirer"
               return jsonify({"message":"logged in","data":{"token":token,"user":{"name":user.get("name"),"purpose":role,"onboarded":user.get("onboarded")}}}),200
            else:
               return jsonify({"message":"login failed"}),400
        else:
            return jsonify({"message":"login failed"}),400
    else:
        return jsonify({"message":"login failed"}),400
    
@app.route('/login-jobseeker', methods=['GET', 'POST'], endpoint="login_job_seeker")
def login_job_seeker():
    form_data = request.get_json(force=True)
    if request.method == 'POST':
        user = user_details_collection.find_one({"email": form_data.get("email")},{"_id": 0})
        if user :
            email = form_data.get("email")
            password = form_data.get("password")
            if password==user.password:
               token = jwt.encode({
               'public_id': user.user_id,
               'exp' : '30000000000000000000000000'
                }, APP_SECRET)
               flash("Successfully Logged In")
               return jsonify({"message":"logged in","data":{"token":"token","onboarded":False}}),200
        else:
            jsonify({"message":"login failed"}),400
    else:
        return jsonify({"message":"login failed"}),400
    
@app.route('/register-hirer', methods=['GET', 'POST'], endpoint="register_hirer")
def register_hirer():
    form_data = request.get_json(force=True) 
    user_id=str(uuid.uuid4())
    if request.method == 'POST':
        user=user_details_collection.find_one({"email": form_data.get('email')},{"_id": 0})
        if user is None:
            email = form_data.get("email")
            password = form_data.get("password")
            name = form_data.get("name")
            user_data = {
                "name":name,
                "user_id":user_id,
                "email": email,
                "password": password,
                "role":"hirer",
                "onboarded":False
            }
            user_details_collection.insert_one(user_data)
            flash("Successfully Registered. U can log in.")
            return jsonify({"message":"user is registered"}),200
        else:
            return jsonify({"message":"user already exists"}),400
    else:
        return render_template("register_hirer.html")
    
@app.route('/register-jobseeker', methods=['GET', 'POST'], endpoint="register_jobseeker")
def register_jobseeker():
    form_data = request.get_json(force=True) 
    user_id=str(uuid.uuid4())
    if request.method == 'POST':
        if user_details_collection.find_one({"email": form_data.get("email")},{"_id": 0}) is None:
            email = form_data.get("email")
            password = form_data.get("password")
            name = form_data.get("name")
            user_details = {
                "name": name,
                "user_id":  user_id,           
                "email": email,
                "password":password,
                "role":"jobseeker",
                "onboarded":False
            }
            user_details_collection.insert_one(user_details)
            return jsonify({"message":"successfully registered"}),200
        else:
            return jsonify({"message": "User already exist!"}),500
    else:
        return render_template("register_job_seeker.html")

@newlogin_is_required
@app.route("/logout-user", methods = ['GET'])
def logout_user():
    if "token" not in session:
        return redirect("/")
    all_keys = list(session.keys())
    for key in all_keys:
        session.pop(key)
    return redirect("/")

@app.route("/mbsa", methods = ['GET'])
def mbsa():
    return str(mbsambsasmbsa())

@app.route("/mbsai", methods = ['GET'])
def mbsa1():
    return render_template('mbsa.html')


@app.route("/billbot", methods = ['GET', 'POST'], endpoint='chatbot')
@newlogin_is_required
@is_candidate
def chatbot(user):
    user_id=user.get("user_id")
    if onboarding_details := onboarding_details_collection.find_one({"user_id": user_id}, {"_id": 0}):
        phase = onboarding_details.get('phase')
        build_status = onboarding_details.get('build_status')
        if phase == "1":
            # messages = list(chatbot_collection.find({},{"_id": 0}))
            resume_uploaded = False
            if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
                if 'resume_link' in profile_details:
                    resume_link = profile_details['resume_link']
                    resume_uploaded = True
            if resume_uploaded:
                messages = [{"user": "billbot","msg": "Hi, I am BillBot."}, {"user": "billbot", "msg": f"I see you have already uploaded a <a href={resume_link} target=_blank>Resume</a>. Click Yes, if you want to upload another resume and hit no to use BillBot to develope a resume using AI!"}]
            else:           
                messages = [{"user": "billbot","msg": "Hi, I am BillBot."}, {"user": "billbot", "msg": "Do you have a pre-built resume?"}]
            return jsonify({"messages":messages,"nxt_build_status":build_status})
        elif phase == "2":
            print(build_status,'build')
            messages = outbound_messages(build_status)
            nxt_build_status = next_build_status(build_status)
            #resume_details_collection.update_one({"user_id": user_id},{"$set":{"resume_json": {"name":"rajesh"}}})
            # messages = [{"user":"billbot","msg": "Hi, The right side of your screen will display your resume. You can give me instruction to build it in the chat."},{"user":"billbot","msg": "You can give me information regarding your inroduction, skills, experiences, achievements and projects. I will create a professional resume for you!"}]
            if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
                resume_html = resume_details.get("resume_html")
                resume_json = resume_details.get("resume_json")
                json_template = resume_details.get("json_template")
                resume_built = True
                return jsonify({"messages":messages,"json_template":json_template, "resume_html":resume_html,"resume_json":resume_json, "resume_built":resume_built, "nxt_build_status":build_status}) 
            else:
                abort(500,{"message":"Something went wrong! Contact ADMIN!"})

@app.route("/edit/mdresume", methods=['GET','POST'], endpoint="edit_mdresume")
@newlogin_is_required
@is_candidate
def edit_mdresume(user):
    user_id = user.get("user_id")
    if request.method == 'POST':
        form_data = dict(request.form)
        resume_html = form_data.get("resume_html")
        resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_html": resume_html}})
        analyze_resume(user_id)
        return redirect("/edit/mdresume")
    if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        markdown = resume_details.get("resume_html")
        return jsonify({"markdown":markdown}) 
    else:
        abort(500, {"messages": f"Resume Deatails for user_id {user_id} unavailable! Contact Admin!"})

@app.route("/resume_build", methods = ['POST'], endpoint='resume_build')
@newlogin_is_required
@is_candidate
def resume_build(user):
    user_id = user.get("user_id")
    form_data = request.get_json(force=True)
    userMsg = form_data.get("msg")
    nxt_build_status = form_data.get("nxt_build_status")
    print(nxt_build_status,'abcd')
    updated_build_status(user_id, nxt_build_status)
    profile_details_collection.update_one({"user_id":user_id},{"$set":{nxt_build_status:userMsg}})
    nxt_build_status_ = next_build_status(nxt_build_status)
    html_code = query_update_billbot(user_id, userMsg, nxt_build_status)
    add_html_to_db(user_id, html_code)
    return {"html_code" :str(html_code), "nxt_messages": outbound_messages(nxt_build_status_), "nxt_build_status": nxt_build_status_}

@app.route("/save_html_resume", methods = ['POST'], endpoint='resume_html')
@newlogin_is_required
@is_candidate
def resume_html(user):
    user_id = user.get("user_id")
    form_data = request.get_json(force=True)
    html = form_data.get("html")
    add_realhtml_to_db(user_id, html)
    return {"html_code" :str(html), "message":"saved html to db"}


@app.route("/current_build_status", methods = ['POST'], endpoint='current_build_status')
@is_candidate
@newlogin_is_required
def current_build_status(user):
    user_id = user.get("user_id")
    if onboarding_details := onboarding_details_collection.find_one({"user_id": user_id}):
        current_build_status = onboarding_details.get("build_status")
        return next_build_status(str(current_build_status))
    else:
        abort(500)

@app.route("/resume_built", methods = ['POST'], endpoint='resume_built')
@newlogin_is_required
@is_candidate
def resume_built(user):
    form_data = request.get_json(force=True) 
    resume_html = form_data.get("resume_html")
    user_id = user.get("user_id")
    onboarding_details_collection.update_one({"user_id": user_id},{"$set": {"resume_built": True}})
    resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_html": resume_html}})
    updated_build_status(user_id,'endofchecklist')
    analyze_resume(user_id)
    return jsonify({"message":"resume is saved"}),200

@app.route("/resume_save", methods = ['POST'], endpoint='resume_save')
@newlogin_is_required
@is_candidate
def resume_save(user):
    form_data = request.get_json(force=True) 
    resume_html = form_data.get("resume_html")
    user_id = user.get("user_id")
    resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_html": resume_html}})
    analyze_resume(user_id)
    return jsonify({"message":"resume is saved"}),200

@app.route('/resume_upload',methods = ['POST'], endpoint='resume_upload')
@is_candidate
@newlogin_is_required
def resume_upload(user):
    user_id = user.get("user_id")
    if 'resume' in request.files:
        resume = request.files['resume']
        resume_link = upload_file_firebase(resume, f"{user_id}/resume.pdf")
        data = {"resume_link": resume_link}
        if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
            resume_details_collection.update_one({"user_id": user_id},{"$set": data})
        else:
            resume_details_collection.insert_one({"user_id": user_id, "resume_link": resume_link})
        profile_details_collection.update_one({"user_id": user_id},{"$set": data})
        onboarding_details_collection.update_one({"user_id": user_id},{"$set": {"resume_built": True}})
        resume_text = extract_text_pdf(resume)
        analyze_resume(user_id, resume_text)
        return jsonify({"message":"resume has been uploaded!"})
    
@app.route('/update_resume',methods = ['POST'], endpoint='update_resume')
@is_candidate
@newlogin_is_required
def update_resume(user):
    user_id = user.get("user_id")
    if 'resume' in request.files:
        resume = request.files['resume']
        resume_link = upload_file_firebase(resume, f"{user_id}/resume.pdf")
        data = {"resume_link": resume_link}
        if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
            resume_details_collection.update_one({"user_id": user_id},{"$set": data})
        else:
            resume_details_collection.insert_one({"user_id": user_id, "resume_link": resume_link})
        profile_details_collection.update_one({"user_id": user_id},{"$set": data})
        resume_text = extract_text_pdf(resume)
        analyze_resume(user_id, resume_text)
        return jsonify({"message":"resume has been updated"})
  
@app.route("/have_resume", methods = ['POST'], endpoint='have_resume')
@is_candidate
@newlogin_is_required
def have_resume(user):
    user_id = user.get("user_id")
    onboarding_details_collection.update_one({"user_id": user_id}, {"$set": {"phase": "2"}})
    data=request.get_json(force=True)
    print(data,'data')
    resume_data = {"user_id": user_id,"resume_html":data.get('resumeFormat'),"json_template":data.get("json_template")}
    resume_details_collection.insert_one(resume_data)
    resume_html,template = get_resume_html_db(user_id)
    profile=profile_details_collection.find_one({"user_id":user_id})
    name=profile.get('name')
    statement="i am"+" "+name
    html_code=query_update_billbot(user_id,statement, 'nxt_build_status_')
    add_html_to_db(user_id, html_code)
    return jsonify({"message":"updated successfully"})

@app.route("/rebuild_resume", methods = ['GET'], endpoint='rebuild_resume')
@is_candidate
@newlogin_is_required
def rebuild_resume(user):
    user_id = user.get("user_id")
    onboarding_details_collection.update_one({"user_id": user_id}, {"$set": {"phase": "1","build_status":"introduction","resume_built":False}})
    resume_details_collection.delete_one({"user_id": user_id})
    return jsonify({"message":"updated successfully"})

@app.route("/allresumes", methods = ['GET'], endpoint='allresumes')
def allresumes():
    resumes=list(resume_details_collection.find({}, {'_id': 0}))
    return jsonify({"resumes":resumes})

@app.route("/all__jobs", methods = ['GET'], endpoint='all__jobs')
def all__jobs():
    jobs=list(task_chat_details_collection.find({}, {'_id': 0}))
    return jsonify({"jobs":jobs})

@app.route("/all-jobs", methods = ['GET'], endpoint='all_jobs')
def all_jobs():
    jobs=list(jobs_details_collection.find({}, {'_id': 0}))
    return jsonify({"jobs":jobs})

@app.route("/allusers", methods = ['GET'], endpoint='allusers')
def allusers():
    users=list(user_details_collection.find({}, {'_id': 0,"password":0}))
    return jsonify({"users":users})

@app.route("/allplans", methods = ['GET'], endpoint='allplans')
def allplans():
    users=list(plans_collection.find({}))
    return jsonify({"users":users})

@app.route("/allhirers", methods = ['GET'], endpoint='allhirers')
def allhirers():
    users=list(user_details_collection.find({"role":"hirer"}, {'_id': 0}))
    pipeline = [
            {"$match": {"role":"hirer","onboarded":True}},
            {
                '$lookup': {
                    'from': 'resume', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'resume_details'
                }
            }, 
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            },
                        {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'onboarding_details'
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'resume_details._id': 0,
                    'user_details._id': 0
                }
            }
        ]
    companies= list(user_details_collection.aggregate(pipeline))
    return jsonify({"hirers":users,"companies":companies})

@app.route("/admin-dashboard", methods = ['GET'], endpoint='admin_dashboard')
def admin_dashboard():
    users=list(user_details_collection.find({"role":"hirer"}, {'_id': 0}))
    pipeline = [
            {"$match": {"role":"hirer","onboarded":True}},
            {
                '$lookup': {
                    'from': 'profile_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'profile_details'
                }
            },
                        {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'onboarding_details'
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'onboarding_details._id': 0,
                    'profile_details._id': 0
                }
            }
        ]
    pipeline_js = [
            {"$match": {"role":"jobseeker","onboarded":True}},
            {
                '$lookup': {
                    'from': 'resume', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'resume_details'
                }
            }, 
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            },
                        {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'onboarding_details'
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'resume_details._id': 0,
                    'user_details._id': 0
                }
            }
        ]
    companies= list(user_details_collection.aggregate(pipeline))
    jobseekers= list(user_details_collection.aggregate(pipeline_js))
    return jsonify({"jobseekers":jobseekers,"companies":companies})

@app.route("/all-chats", methods = ['GET'], endpoint='allchats')
def allchats():
    connections=list(connection_details_collection.find({},{'_id':0}))
    chats=list(chat_details_collection.find({}, {'_id': 0}))
    return jsonify({"chats":chats,"connections":connections})

@app.route("/allonboarding", methods = ['GET'], endpoint='allonboarding')
def allonboarding():
    users=list(onboarding_details_collection.find({}, {'_id': 0}))
    return jsonify({"users":users})


@app.route("/allprofiles", methods = ['GET'], endpoint='allprofiles')
def allprofiles():
    users=list(profile_details_collection.find({}, {'_id': 0}))
    return jsonify({"users":users})

@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )
    # return redirect("/mbsa")
    user_id = id_info.get("sub")
    user_name = id_info.get("name")
    user_email = id_info.get("email")
    data = {
        "google_id": user_id,
        "name": user_name,
        "email": user_email,
        "onboarded": False,
    }
    session.update(data)
    pipeline = [
            {
                '$match': {
                    'user_id': str(user_id)
                }
            }, {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'onboarding_details'
                }
            }, {
                '$project': {
                    '_id': 0, 
                    'onboarding_details._id': 0
                }
            }
        ]
    
    if user_details := list(user_details_collection.aggregate(pipeline)):
        user_details = user_details[0]
        session["onboarded"] = user_details.get("onboarded")
        onboarding_details = user_details.get("onboarding_details")
        if onboarding_details:
            onboarding_details = onboarding_details[0]
            session["purpose"] = onboarding_details.get("purpose")
            purpose = session["purpose"]
            if purpose and purpose == "jobseeker":
                session["resume_built"] = onboarding_details.get("resume_built")
    else:
        user_data = {
            "user_id": id_info.get("sub"),
            "user_name": id_info.get("name"),
            "email": id_info.get("email"),
            "joined_at": datetime.now(),
            "onboarded": False
        }
        session["onboarded"] = user_data.get("onboarded")
        user_details_collection.insert_one(user_data)
    return redirect("/")

@app.route("/onboarding-hirer", methods=['GET', 'POST'],endpoint='onboarding_hirer')
@newlogin_is_required
def onboarding_hirer(user):
    user_id=user.get("user_id")
    if request.method == 'POST':
        if  user_id is None:
            abort(401)
        else:
            onboarding_details = dict(request.form)
            purpose=''
            if user_details := user_details_collection.find_one({"user_id": user_id},{"_id": 0,'password':0}):
             if user_details.get('role')=='hirer':
                purpose='hirer'
             onboarding_details['user_id'] = user_id
             if user_details.get("onboarded") == False:
                    data = {"onboarded": True,"subscription":"basic"}
                    onboarding_details['status'] = "active"
                    if purpose and purpose == "hirer":
                        profile_data = {
                            "user_id": user_details.get("user_id"),
                            "company_name": onboarding_details.get("company_name"),
                            "email": user_details.get("email"),
                            "company_representative_mobno": onboarding_details.get("company_representative_mobno"),
                        }
                        if 'company_logo' in request.files and str(request.files['company_logo'].filename)!="":
                            company_logo = request.files['company_logo']
                            company_logo_link = upload_file_firebase(company_logo, f"{user_id}/company_logo.png")
                            profile_data['company_logo'] = company_logo_link
                        profile_details_collection.insert_one(profile_data)
                        onboarding_details['approved_by_admin'] = True
                    else:
                        abort(500, {"message": "Onboarding couldn't be completed due to some technical issue!"})
                    onboarding_details_collection.insert_one(onboarding_details)
                    user_details_collection.update_one({"user_id": user_id}, {"$set":data})
                    return jsonify({"message":"successfully onboarded"}),200
             else:
                    abort(500, {"message": "User already Onboarded."})
    onboarded = user.get('onboarded')
    if onboarded == True:
        purpose = user.get("role")
        return jsonify({"message":"onboarded successfully"}),200
    user_name = user.get("name")
    return jsonify({'user_name':user_name})

@app.route("/onboarding-jobseeker", methods=['GET', 'POST'],endpoint='onboarding_jobseeker')
@newlogin_is_required
def onboarding_jobseeker(user):
    user_id=user.get("user_id")
    if request.method == 'POST':
        if  user_id is None:
            abort(401)
        else:
            onboarding_details = request.get_json(force=True)
            if user_details := user_details_collection.find_one({"user_id": user_id},{"_id": 0,'password':0}):
             if user_details.get('role')=='jobseeker':
                     purpose='jobseeker'
             if user_details.get('role')=='hirer':
                     purpose='hirer'
             onboarding_details['user_id'] = user_id
             if user_details.get("onboarded") == False:
                    data = {"onboarded": True}
                    onboarding_details['status'] = "active"
                    if purpose and purpose == "jobseeker":
                        onboarding_details['phase'] = "1"
                        onboarding_details['build_status'] = "introduction"
                        onboarding_details['resume_built'] = False
                        profile_data = {
                            "user_id": user_details.get("user_id"),
                            "name": user_details.get("name"),
                            "email": user_details.get("email"),
                            "mobno": onboarding_details.get("candidate_mobno"),
                            "education":onboarding_details.get("education"),
                            "experience":onboarding_details.get("experience")
                        }
                        profile_details_collection.insert_one(profile_data)
                    elif purpose and purpose == "hirer":
                        profile_data = {
                            "user_id": user_details.get("user_id"),
                            "company_name": onboarding_details.get("company_name"),
                            "email": user_details.get("email"),
                            "company_representative_mobno": onboarding_details.get("company_representative_mobno"),
                        }
                        if 'company_logo' in request.files and str(request.files['company_logo'].filename)!="":
                            company_logo = request.files['company_logo']
                            company_logo_link = upload_file_firebase(company_logo, f"{user_id}/company_logo.png")
                            profile_data['company_logo'] = company_logo_link
                        profile_details_collection.insert_one(profile_data)
                        onboarding_details['approved_by_admin'] = True
                    else:
                        abort(500, {"message": "Onboarding couldn't be completed due to some technical issue!"})
                    onboarding_details_collection.insert_one(onboarding_details)
                    user_details_collection.update_one({"user_id": user_id}, {"$set":data})
                    return jsonify({"message":"successfully onboarded"}),200
             else:
                    abort(500, {"message": "User already Onboarded."})
    onboarded = user.get('onboarded')
    if onboarded == True:
        purpose = user.get("role")
        return jsonify({"message":"onboarded successfully"})
    user_name = user.get("name")
    return jsonify({'user_name':user_name})

@app.route("/onboarding_details", methods=['GET', 'POST'],endpoint='onboarding_details')
@newlogin_is_required
def onboarding_details(user):
    user_id=user.get('user_id')
    onboarding=onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    return jsonify({'onboarding':onboarding})

@app.route("/all_companies", methods=['GET', 'POST'],endpoint='all_onboarding_details')
def all_onboarding_details():
    companies=list(onboarding_details_collection.find({},{"_id": 0}))
    #profiles=list(profile_details_collection.find({},{"_id": 0}))
    pipeline = [
            {
                '$match': {"role":"hirer","onboarded":True}
            }, {
                '$lookup': {
                    'from': 'jobs_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'jobs_details'
                }
            },
            {
                '$lookup': {
                    'from': 'profile_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'profile_details'
                }
            },
              {
                '$project': {
                    '_id': 0, 
                    'jobs_details._id': 0,
                    'profile_details._id':0
                }
            }
        ]
    
    profiles = list(user_details_collection.aggregate(pipeline))
    return jsonify({'companies':companies,'profiles':profiles})
    
@app.route('/create_job',methods=['POST'], endpoint="create_job")
@is_hirer
@newlogin_is_required
def create_job(user):
    user_id = user.get("user_id")
    job_id = str(uuid.uuid4())
    job_details = request.get_json(force=True)
    job_details['user_id'] = user_id
    job_details['job_id'] = job_id
    job_details['created_on'] = datetime.now()
    jobs_details_collection.insert_one(job_details)
    return jsonify({'status': 'success', 'message': 'Job created successfully'})

@app.route('/edit/job/<string:job_id>', methods=['GET', 'POST'], endpoint="edit_job")
@newlogin_is_required
@is_hirer
def edit_job(user,job_id):
    user_id = user.get("user_id")
    if request.method == 'POST':
        incoming_details = request.get_json(force=True)
        jobs_details_collection.update_one({"user_id": str(user_id), "job_id": str(job_id)},{"$set": incoming_details})
        return jsonify({"message":"job is updated successfully!"})
    if job_details := jobs_details_collection.find_one({"user_id": str(user_id), "job_id": str(job_id)},{"_id": 0}):
        return jsonify({'job_details':job_details})
    
@app.route('/delete/job/<string:job_id>', methods=['POST'], endpoint="delete_job")
@newlogin_is_required
@is_hirer
def delete_job(user,job_id):
    user_id = user.get("user_id")
    if request.method == 'POST':
        jobs_details_collection.delete_one({"user_id": str(user_id), "job_id": str(job_id)})
        return jsonify({"message":"job deleted successfully"}),200

@app.route('/save/job/<string:job_id>', methods=['POST'], endpoint="save_job")
@newlogin_is_required
@is_candidate
def save_job(user,job_id):
    user_id = user.get("user_id")
    if _ := saved_jobs_collection.find_one({"user_id": user_id, "job_id": job_id},{"_id": 0}):
        return "error",400
    else:
        saved_job_data = {
            "user_id": user_id,
            "job_id": job_id,
            "saved_on": datetime.now()
        }
        saved_jobs_collection.insert_one(saved_job_data)
        return {"status": "saved"}
    
@app.route('/create_task',methods=['POST'], endpoint="create_task")
@newlogin_is_required
def create_task(user):
    user_id = user.get("user_id")
    task_id = str(uuid.uuid4())
    task_details = request.get_json(force=True)
    task_details['user_id'] = user_id
    task_details['task_id'] = task_id
    task_details['created_on'] = datetime.now()
    task_details['budget']=int(task_details['budget'])
    tasks_details_collection.insert_one(task_details)
    return jsonify({"message":"task created successfully"}),200
    
@app.route('/edit/task/<string:task_id>', methods=['GET', 'POST'], endpoint="edit_task")
@newlogin_is_required
def edit_task(user,task_id):
    user_id = user.get("user_id")
    if request.method == 'POST':
        incoming_details = request.get_json(force=True)
        tasks_details_collection.update_one({"user_id": str(user_id), "task_id": str(task_id)},{"$set": incoming_details})
        return jsonify({"message":"task editedd successfully"}),200
    if task_details := tasks_details_collection.find_one({"user_id": str(user_id), "task_id": str(task_id)},{"_id": 0}):
        return jsonify({"task_details":task_details})
    

@app.route('/remove_saved_job/<string:job_id>', methods=['POST'], endpoint="remove_saved_job")
@newlogin_is_required
@is_candidate
def remove_saved_job(user,job_id):
    user_id = user.get("user_id")
    if _ := saved_jobs_collection.find_one({"user_id": user_id, "job_id": job_id},{"_id": 0}):
        saved_jobs_collection.delete_one({"user_id": user_id, "job_id": job_id})
        return {"status": "deleted"}
    else:
        return "error",400


@app.route('/apply/job/<string:job_id>', methods=['GET', 'POST'], endpoint="apply_job")
@newlogin_is_required
@is_candidate
def apply_job(user,job_id):
    user_id = user.get("user_id")
    if request.method == 'POST':
        if job_details := jobs_details_collection.find_one({"job_id": job_id},{"_id": 0}):
            job_apply_data = {
                "job_id": job_id,
                "hirer_id": job_details.get("user_id"),
                "user_id": user_id,
                "applied_on": datetime.now(),
                "updated_at": datetime.now(),
                "status": "Applied",
                "seen": False
            }
            if candidate_job_application_collection.find_one({"user_id": user_id, "job_id": job_id},{"_id": 0}):
               return jsonify({"success":False, "message":"applied already"}),400
            candidate_job_application_collection.insert_one(job_apply_data)
            new=len(list(candidate_job_application_collection.find({"job_id":job_id,"seen":False})))
              # Update or create job-specific notification
            notification_collection.update_one(
        {
            "user_id": job_details["user_id"],
            "type": "job",
            "related_id": str(job_id)
        },
        {
            "$set": {
                "type": "job",
                "message": f"{new} new applicants for '{job_details['job_title']}'",
                "related_id": str(job_id),
                "updated_at": datetime.now(),
                "is_read": False,
                "is_new": True
            },
            "$inc": {"new_applicants_count": 1}  # Increment new applicant count
        },
        upsert=True
    )
            flash("Successfully Applied for the Job. Recruiters will get back to you soon, if you are a good fit.")
            return jsonify({"success":True, "applied":True})
        else:
            abort(500,{"messages": f"Job with Job Id {job_id} doesn't exist! "})
    pipeline = [
              {"$match": {"job_id": str(job_id)}},
                {
                    '$lookup': {
                        'from': 'onboarding_details', 
                        'localField': 'user_id', 
                        'foreignField': 'user_id', 
                        'as': 'user_details'
                    }
                }, 
                                {
                    '$lookup': {
                        'from': 'profile_details', 
                        'localField': 'user_id', 
                        'foreignField': 'user_id', 
                        'as': 'company_details'
                    }
                },
                {
                    '$project': {
                        '_id': 0,
                        'user_details._id': 0
                    }
                }
            ]
    if job_details := list(jobs_details_collection.aggregate(pipeline)):
        job_details = job_details[0]
        if job_details.get("status") == "published":
            if candidate_job_application_collection.find_one({"user_id": user_id, "job_id": job_id},{"_id": 0}):
               applied = True 
            else:
                applied = False
            return jsonify({"job_details":job_details, "applied":applied})
        else:
            abort(500, {"message": f"JOB with job_id {job_id} not found!"})
    else:
        abort(500, {"message": f"JOB with job_id {job_id} not found!"})

@app.route("/status/job/<string:candidate_user_id>", methods=['POST'])
@newlogin_is_required
@is_hirer
def change_job_status(user,candidate_user_id):
    form_data = request.get_json(force=True)
    status = form_data.get("status")
    job_id = form_data.get("job_id")
    candidate_job_application_collection.update_one({"job_id": job_id, 'user_id': candidate_user_id},{"$set": {"status": status,"updated_at":datetime.now()} })
    notification={
    "notification_id": str(uuid.uuid4()),
    "user_id": candidate_user_id,
    "type": "application",
    "message": f"Your application has been {status}!",
    "job_id": job_id,
    "is_read": False,
    "is_new": True,
    "created_at": datetime.now()
     }
    notification_collection.insert_one(notification)
    return {"success":True,"message":"status updated successfully"}


@app.route('/responses/job/<string:job_id>', methods=['GET', 'POST'], endpoint="job_responses")
@newlogin_is_required
@is_hirer
@is_onboarded
def job_responses(user,job_id):
    if job_details := jobs_details_collection.find_one({"job_id": job_id},{"_id": 0, "job_title" :1, "mode_of_work": 1}):
        pageno = request.args.get("pageno")
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(candidate_job_application_collection.find({"job_id": job_id})))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
            {
                "$match": {"job_id": job_id}
            },
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'candidate_details'
                }
            },
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            },
             {
                '$lookup': {
                    'from': 'resume', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'resume_details'
                }
            },
           {
        '$project': {
            '_id': 0, 
            'user_details._id': 0,
            'candidate_details._id': 0,
        },
    },{
        '$sort':{'applied_on':-1}
    }
        ]
        all_responses = list(candidate_job_application_collection.aggregate(pipeline))
        candidate_job_application_collection.update_many({"job_id":job_id},{"$set":{"seen":True}})
        return jsonify({"job_id":job_id, "all_responses":all_responses, "job_details":job_details, "total_pages":total_pages, "page_number":page_number})
    


@app.route('/all-job-responses', methods=['GET', 'POST'], endpoint="all_job_responses")
@newlogin_is_required
@is_hirer
@is_onboarded
def all_job_responses(user):
        pageno = request.args.get("pageno")
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(candidate_job_application_collection.find()))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'candidate_details'
                }
            },
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            },
             {
                '$lookup': {
                    'from': 'resume', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'resume_details'
                }
            },
           {
        '$project': {
            '_id': 0, 
            'user_details._id': 0,
            'candidate_details._id': 0,
        },
    },{
        '$sort':{'applied_on':-1}
    }
        ]
        all_responses = list(candidate_job_application_collection.aggregate(pipeline))
        return jsonify({"all_responses":all_responses, "total_pages":total_pages, "page_number":page_number})
    
@app.route('/all-candidates', methods=['GET', 'POST'], endpoint="all_candidates")
@newlogin_is_required
@is_hirer
@is_onboarded
def all_candidates(user):
        pageno = request.args.get("pageno")
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(candidate_job_application_collection.find()))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
                      {
                "$match": {"role": "jobseeker"}
            },
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'candidate_details'
                }
            },
             {
                '$lookup': {
                    'from': 'resume', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'resume_details'
                }
            },
           {
        '$project': {
            '_id': 0, 
            'user_details._id': 0,
            'candidate_details._id': 0,
            'resume_details._id':0
        },
    },{
        '$sort':{'applied_on':-1}
    }
        ]
        all_responses = list(user_details_collection.aggregate(pipeline))
        return jsonify({"all_responses":all_responses, "total_pages":total_pages, "page_number":page_number})
    
@app.route("/alltasks", methods = ['GET'], endpoint='alltasks')
@newlogin_is_required
def alltasks(user):
    user_name = user.get("name")
    onboarded = user.get("onboarded")
    user_id = user.get("user_id")
    if onboarded == False:
        return redirect("/onboarding")
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    pageno = request.args.get("pageno")
    page_number = 1  # The page number you want to retrieve
    if pageno is not None:
        page_number = int(pageno)
    page_size = 7   # Number of documents per page
    total_elements = len(list(tasks_details_collection.find({},{"_id": 0})))
    total_pages = calculate_total_pages(total_elements, page_size)
    skip = (page_number - 1) * page_size
    pipeline = [
        {
            '$lookup': {
                'from': 'tasks_details', 
                'localField': 'task_id', 
                'foreignField': 'task_id', 
                'as': 'task_details'
            }
        }, 
        {
            '$lookup': {
                'from': 'candidate_task_proposal', 
                'localField': 'task_id', 
                'foreignField': 'task_id', 
                'as': 'proposals'
            }
        }, 
        {
            '$project': {
                '_id': 0,
                'task_details._id': 0,
                'proposals._id':0
            }
        },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
    ]
    all_tasks = list(tasks_details_collection.aggregate(pipeline))
    # return all_applied_jobs
    return jsonify({"user_name":user_name, "onboarding_details":onboarding_details, "all_tasks":all_tasks, "total_pages":total_pages,"page_number":page_number})

@app.route("/filterTasks", methods=['GET'], endpoint="filter__tasks")
@newlogin_is_required
def filter_tasks(user):
    user_id=user.get('user_id')
    searched_for = request.args.get("search")
    task_title=request.args.get("task_title")
    budget_from=request.args.get("budget_from")
    budget_to=request.args.get("budget_to")
    category=request.args.get("category")
    task_topics=request.args.get("task_topics")
    print(budget_from,'argse')
    query = {}
    query['status'] = 'published'
    if task_title:
        query['task_title'] = {"$regex": task_title, "$options": "i"}
    if budget_from:
       query['budget'] = {"$gte":int(budget_from)}
    if budget_to:
       query['budget'] = {"$lt":int(budget_to)}
    if budget_to and budget_from:
        query['budget'] = {"$gte":int(budget_from),"$lt":int(budget_to)}
    if category:
        query['category'] = category
    if task_topics:  # Get tags from query parameters, e.g., tags=#java&tags=#react
            tags = [f"#{re.escape(tag.strip())}" for tag in task_topics.split(',')]
            regex_pattern = '|'.join([f"{tag}" for tag in tags])
            query ["task_topics"]= {"$regex": regex_pattern, "$options": "i"}
            #query['task_topics']={'$regex': '#python', '$options': 'i'}

    pipeline = [ {
            '$lookup': {
                'from': 'candidate_task_proposal', 
                'localField': 'task_id', 
                'foreignField': 'task_id', 
                'as': 'proposals'
            }
        }, 
        {
            '$project': {
                '_id': 0,
                'proposals._id':0
            }
        },
    ]
    if searched_for:
        pipeline.append({
            "$match": {
                "$or": [
                    {"task_title": {"$regex": searched_for, "$options": "i"}},
                    {"task_topics": {"$regex": searched_for, "$options": "i"}},
                    {"task_description": {"$regex": searched_for, "$options": "i"}},
                    {"task_category": {"$regex": searched_for, "$options": "i"}}
                ]
            }
        })
    if query:
        print(query,'querying')
        pipeline.append({"$match": query})
    #elif query:
     #   pipeline.append({"$match": query})

    # Add the lookup and project stages
    pipeline.extend([
        {
            '$project': {
                '_id': 0,
            }
        }
    ])
    print(pipeline,'tasks')
    all_tasks = list(tasks_details_collection.aggregate(pipeline))
    #print(all_tasks,'tasks')
    all_updated_tasks = []
    for idx, task in enumerate(all_tasks):
            applied = candidate_task_proposal_collection.find_one({"task_id": task.get("task_id"), "user_id": user_id}, {"_id": 0})
            own = tasks_details_collection.find_one({"task_id": task.get("task_id"), "user_id": user_id}, {"_id": 0})
            if applied:
                  print(applied,'applied')
                  pass
            elif own:
                  print(own,'own')
                  pass
            if not applied and not own:
                  all_updated_tasks.append(task)
    return jsonify({'all_tasks': all_updated_tasks})

# View a Task details Faizan
@app.route('/view/task/<string:task_id>', methods=['GET'], endpoint="view_task")
@newlogin_is_required
def view_task(user, task_id):
    viewer_name = user.get("name")
    viewer_id = user.get("user_id")
    onboarded = user.get("onboarded")
    if not onboarded:
        return jsonify({"message": "User not onboarded"}), 403
    task_details = tasks_details_collection.find_one({"task_id": task_id}, {"_id": 0})
    if not task_details:
        return jsonify({"message": "Task not found"}), 404
    #Get Poster Details bu searching user_id to mongdb _id
    hirer_id = task_details.get("user_id")
    print(task_details,'hirerid')
    poster_name = user_details_collection.find_one({"user_id": hirer_id}, {"_id": 0,'password':0})
    if not poster_name:
        return jsonify({"message": "Poster not found"}), 404
       # Fetch task details
    task_pipeline = [
        {"$match": {"task_id": str(task_id)}},
        {
            '$lookup': {
                'from': 'onboarding_details', 
                'localField': 'user_id', 
                'foreignField': 'user_id', 
                'as': 'user_details'
            }
        }, 
            {
            '$lookup': {
                'from': 'user_details', 
                'localField': 'user_id', 
                'foreignField': 'user_id', 
                'as': 'hirer_details'
            }
        },
        {"$lookup": {
        "from": "tasks_details",
        "let": {"user_id": "$user_id"},
        "pipeline": [
            {"$match": {"$expr": {"$eq": ["$user_id", "$$user_id"]}}},
            {"$group": {
                "_id": "$user_id",
                "total_tasks_posted": {"$sum": 1},
                "total_spent": {"$sum": "$budget"}  # Assumes `cost` field in tasks_details_collection
            }}
        ],
        "as": "user_task_summary"
    }},
        {
        # Add average rating field to user_details by calculating from proposer_reviews
        "$addFields": {
            "hirer_details": {
                "$map": {
                    "input": "$hirer_details",
                    "as": "user",
                    "in": {
                        "$mergeObjects": [
                            "$$user",
                            {
                                "average_review": {
                                    "$cond": {
                                        "if": { "$gt": [{ "$size": { "$ifNull": ["$$user.hirer_reviews", []] } }, 0] },
                                        "then": { 
                                            "$avg": "$$user.hirer_reviews.stars" 
                                        },
                                        "else": None  # Set to None if there are no reviews
                                    }
                                },
                                "total_reviews": { "$size": { "$ifNull": ["$$user.hirer_reviews", []] } },  # Count of reviews
                            }
                        ]
                    }
                }
            }
        }
    },
            {
            '$project': {
                '_id': 0,
                'user_details._id': 0,
                'hirer_details._id': 0
            }
        },
    ]
    
    task_details_ = list(tasks_details_collection.aggregate(task_pipeline))
    applied=False
    if hirer_id==viewer_id:
       applied=True
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id,"user_id":viewer_id}, {"_id": 0})
    if proposal:
       applied=True
    print(applied,proposal,'pro')
    task_details["applied"]=applied
    for task in task_details_:
        task["applied"] = applied
        task["poster_user_name"] = poster_name.get("name")
    task_seen_by_collection.update_one({"task_id": task_id}, {"$addToSet": {"seen_by": {"viewer_id": viewer_id, "viewer_name": viewer_name}}})
    return jsonify({"task_details": task_details_}), 200

@app.route('/update/task/<string:task_id>', methods=['POST'], endpoint="update_task")
@newlogin_is_required
def update_task(user, task_id):
    viewer_name = user.get("name")
    viewer_id = user.get("user_id")
    onboarded = user.get("onboarded")
    form_data = request.get_json(force=True)
    status = form_data.get("status")
    if not onboarded:
        return jsonify({"message": "User not onboarded"}), 403
    task_details = tasks_details_collection.find_one({"task_id": task_id}, {"_id": 0})
    if not task_details:
        return jsonify({"message": "Task not found"}), 404
    #Get Poster Details bu searching user_id to mongdb _id
    tasks_details_collection.update_one({"task_id": task_id}, {"$set": {"status": status}})
    return jsonify({"task_details": task_details}), 200

@app.route('/apply/task/<string:task_id>', methods=['GET', 'POST'], endpoint="apply_task")
@newlogin_is_required
def apply_task(user,task_id):
    user_id = user.get("user_id")
    
    # Fetch existing proposals for the task
    proposals_pipeline = [
        {
            '$lookup': {
                'from': 'candidate_task_proposal', 
                'localField': 'task_id', 
                'foreignField': 'task_id', 
                'as': 'task_details'
            }
        }, 
        {
            '$project': {
                '_id': 0,
                'task_details._id': 0
            }
        }
    ]
    proposals = list(candidate_task_proposal_collection.aggregate(proposals_pipeline))
    
    if request.method == 'POST':
        if task_details := tasks_details_collection.find_one({"task_id": task_id},{"_id": 0}):
            form_data = request.get_json(force=True)
            quote = form_data.get("quote")
            deposit = form_data.get("deposit")
            message = form_data.get("message")
            
            task_apply_data = {
                "task_id": task_id,
                "hirer_id": task_details.get("user_id"),
                "user_id": user_id,
                "applied_on": datetime.now(),
                "status": "Applied",
                "message":message,
                "quote":quote,
                "deposit":deposit
            }
            candidate_task_proposal_collection.insert_one(task_apply_data)
            flash("Successfully Applied for the Job. Recruiters will get back to you soon, if you are a good fit.")
            return jsonify({"message":"successfully applied for the task"})
        else:
            return jsonify({"message": f"Job with Job ID {task_id} doesn't exist!"}), 404
    
    # Increment views for the task
    tasks_details_collection.update_one({"task_id": task_id}, {"$inc": {"views": 1}})
    
    # Fetch task details
    task_pipeline = [
        {"$match": {"task_id": str(task_id)}},
        {
            '$lookup': {
                'from': 'onboarding_details', 
                'localField': 'user_id', 
                'foreignField': 'user_id', 
                'as': 'user_details'
            }
        }, 
            {
            '$lookup': {
                'from': 'user_details', 
                'localField': 'user_id', 
                'foreignField': 'user_id', 
                'as': 'hirer_details'
            }
        },
        {
        # Add average rating field to user_details by calculating from proposer_reviews
        "$addFields": {
            "hirer_details": {
                "$map": {
                    "input": "$hirer_details",
                    "as": "user",
                    "in": {
                        "$mergeObjects": [
                            "$$user",
                            {
                                "average_review": {
                                    "$cond": {
                                        "if": { "$gt": [{ "$size": { "$ifNull": ["$$user.proposer_reviews", []] } }, 0] },
                                        "then": { 
                                            "$avg": "$$user.proposer_reviews.stars" 
                                        },
                                        "else": None  # Set to None if there are no reviews
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    },
            {
            '$project': {
                '_id': 0,
                'user_details._id': 0
            }
        },
    ]
    
    job_details = list(tasks_details_collection.aggregate(task_pipeline))
    
    if job_details:
        task_details = job_details[0]
        if task_details.get("status") == "published":
            if candidate_task_proposal_collection.find_one({"user_id": user_id, "task_id": task_id},{"_id": 0}):
               applied = True 
            else:
                applied = False
            return jsonify({"proposals":proposals,"task_details":task_details,"applied":applied})
        else:
            abort(500, {"message": f"JOB with job_id {task_id} not found!"})
    else:
        abort(500, {"message": f"JOB with job_id {task_id} not found!"})

#functions to get tasks of hirers, and job seekrs
def get_tasks(user):
    user_id = user.get("user_id")
    tasks = list(tasks_details_collection.find({"user_id": str(user_id)}))
    return tasks

#API TO GET TASKS
@app.route('/tasks/get', methods=['GET'], endpoint="get_tasks")
@newlogin_is_required
def get_tasks(user):
    user_id = user.get("user_id")
    #tasks = list(tasks_details_collection.find({"user_id": str(user_id)}))
    pipeline = [
            {
                "$match": {"user_id": user_id}
            },
            {
                '$lookup': {
                    'from': 'candidate_task_proposal', 
                    'localField': 'task_id', 
                    'foreignField': 'task_id', 
                    'as': 'proposals'
                }
            },
            {
                '$lookup': {
                    'from': 'task_seen_by', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'views'
                }
            },
           {
        '$project': {
            '_id': 0, 
            'user_details._id': 0,
            'candidate_details._id': 0,
        },
    } # Limit the number of documents per page
        ]
    tasks = list(tasks_details_collection.aggregate(pipeline))
    return jsonify({"tasks":tasks})


#Accept Proposal for a task
@app.route('/proposals/accept/<string:task_id>', methods=['POST'], endpoint="accept_proposal")
@newlogin_is_required
@is_onboarded
def accept_proposal(user,task_id):
    form_data = request.get_json(force=True)
    user_id =  form_data.get("proposer_id")
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id, "user_id": user_id},{"_id": 0})
    print(proposal,'proposal')
    if proposal:
        deposit=int(proposal.get("deposit"))
        proposer_id=form_data.get("proposer_id")
        hirer_id=user.get("user_id")
        candidate_task_proposal_collection.update_one({"task_id": task_id, "user_id": user_id}, {"$set": {"status": "Accepted"}})
        chat_details = {
            "hirer_id": user.get("user_id"),
            "proposer_id": proposal.get("user_id"),
            "task_id": task_id,
            "sent_by": user.get("user_id"),
            "sent_on": datetime.now(),
            "msg": "your proposal has been accepted",
            "seen":False,
            "type":"msg"
        }
        task_chat_details_collection.insert_one(chat_details)
        tasks_details_collection.update_one({"task_id":task_id},{"$set": {"status": "inProgress"}})
        user_details_collection.update_one(
    {"user_id": proposer_id},
    {"$set": {"seller_lock": 0}}
)
        user_details_collection.update_one(
        {"user_id": proposer_id},
          {
          # Set wallet to 0 if it doesn't exist
        "$inc": {"seller_lock": deposit}  # Increment wallet by the budget amount
         },
           upsert=True  # Use upsert to ensure the user document is created if it doesn't exist
          )
        user_details_collection.update_one(
        {"user_id": hirer_id},
          {  # Set wallet to 0 if it doesn't exist
        "$inc": {"buyer_lock": deposit}  # Increment wallet by the budget amount
         },
           upsert=True  # Use upsert to ensure the user document is created if it doesn't exist
          )
        return jsonify({"message": "Proposal accepted successfully"}), 200
    else:
        return jsonify({"message": f"Proposal not found for user {user_id} and task {task_id}"}), 404

#Reject Proposal for a task

@app.route('/proposals/reject/<string:task_id>', methods=['POST'], endpoint="reject_proposal")
@newlogin_is_required
@is_onboarded
def reject_proposal(user,task_id):
    form_data = request.get_json(force=True)
    user_id = form_data.get("proposer_id")
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id, "user_id": user_id},{"_id": 0})
    if proposal:
        candidate_task_proposal_collection.update_one({"task_id": task_id, "user_id": user_id}, {"$set": {"status": "Rejected"}})
        return jsonify({"message": "Proposal rejected successfully"}), 200
    else:
        return jsonify({"message": f"Proposal not found for user {user_id} and task {task_id}"}), 404

#Whitelist a proposal
@app.route('/proposals/workstream/<string:task_id>', methods=['POST'], endpoint="whitelist_proposal")
@newlogin_is_required
@is_onboarded
def whitelist_proposal(user,task_id):
    user_id = user.get("user_id")
    form_data = request.get_json(force=True)
    candidate_id=form_data.get("proposer_id")
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id,"user_id":candidate_id},{"_id": 0})
    if proposal:
        candidate_task_proposal_collection.update_one({"task_id": task_id, "user_id": candidate_id}, {"$set": {"status": "workstream"}})
        return jsonify({"message": "Proposal whitelisted successfully"}), 200
    else:
         return jsonify({"message": f"Proposal not found for user {candidate_id} and task {task_id}"})

@app.route('/proposals/shortlist/<string:task_id>', methods=['POST'], endpoint="shortlist_proposal")
@newlogin_is_required
@is_onboarded
def shortlist_proposal(user,task_id):
    user_id = user.get("user_id")
    form_data = request.get_json(force=True)
    candidate_id=form_data.get("proposer_id")
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id,"user_id":candidate_id},{"_id": 0})
    if proposal:
        candidate_task_proposal_collection.update_one({"task_id": task_id, "user_id": candidate_id}, {"$set": {"status": "shortlisted"}})
        return jsonify({"message": "Proposal whitelisted successfully"}), 200
    else:
         return jsonify({"message": f"Proposal not found for user {candidate_id} and task {task_id}"})

@app.route('/proposals/complete-request/<string:task_id>', methods=['POST'], endpoint="complete_request")
@newlogin_is_required
@is_onboarded
def complete_request(user,task_id):
    form_data = request.get_json(force=True)
    user_id =  form_data.get("proposer_id")
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id, "user_id": user_id},{"_id": 0})
    print(proposal,'proposal')
    if proposal:
        candidate_task_proposal_collection.update_one({"task_id": task_id, "user_id": user_id}, {"$set": {"status": "Accepted"}})
        chat_details = {
            "hirer_id": proposal.get("hirer_id"),
            "proposer_id": proposal.get("user_id"),
            "task_id": task_id,
            "sent_by": user.get("user_id"),
            "sent_on": datetime.now(),
            "msg": "i completed project",
            "seen":False,
            "type":"complete-request"
        }
        task_chat_details_collection.insert_one(chat_details)
        return jsonify({"message": "Proposal accepted successfully"}), 200
    else:
        return jsonify({"message": f"Proposal not found for user {user_id} and task {task_id}"}), 404

@app.route('/proposals/project-completed/<string:task_id>', methods=['POST'], endpoint="project_completed")
@newlogin_is_required
@is_onboarded
def project_completed(user,task_id):
    form_data = request.get_json(force=True)
    user_id =  form_data.get("proposer_id")
    hirer_id=user.get("user_id")
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id, "user_id": user_id},{"_id": 0})
    if proposal:
        print(task_id,'proposal')
        #candidate_task_proposal_collection.update_one({"task_id": task_id, "user_id": user_id}, {"$set": {"status": "Accepted"}})
        task= tasks_details_collection.find_one({"task_id": task_id}, {"_id":0})
        tasks_details_collection.update_one({"task_id": task_id}, {"$set": {"status": "Completed"}})
        wallet_increase=int(task.get("budget"))-int(proposal.get("deposit"))
        lock_decrease=int(proposal.get("deposit"))
        user_details_collection.update_one({"user_id":user_id},{ "$inc":{"wallet":wallet_increase,"seller_lock":-lock_decrease}})
        user_details_collection.update_one({"user_id":hirer_id},{ "$inc":{"buyer_lock":-lock_decrease}})
        return jsonify({"message": "Proposal accepted successfully","task":task}), 200
    else:
        return jsonify({"message": f"Proposal not found for user {user_id} and task {task_id}"}), 404

@app.route('/hirer/task-review/<string:task_id>', methods=['POST'], endpoint="task_review_hirer")
@newlogin_is_required
@is_onboarded
def task_review_hirer(user,task_id):
    form_data = request.get_json(force=True)
    user_id =  form_data.get("proposer_id")
    stars =  form_data.get("rating")
    message =  form_data.get("text")
    review={
        "task_id":task_id,
        "stars":stars,
        "message":message,
        "date":datetime.now()
    }
    user_details_collection.update_one({"user_id": user_id}, {"$push": {"proposer_reviews": review}})
    tasks_details_collection.update_one({"task_id": task_id}, {"$set":{"proposer_review": review}})
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id, "user_id": user_id},{"_id": 0})
    print(proposal,'proposal')
    if proposal:
        chat_details = {
            "hirer_id": proposal.get("hirer_id"),
            "proposer_id": proposal.get("user_id"),
            "task_id": task_id,
            "sent_by": user.get("user_id"),
            "sent_on": datetime.now(),
            "msg": message,
            "rating":stars,
            "seen":False,
            "type":"review"
        }
        task_chat_details_collection.insert_one(chat_details)
        tasks_details_collection.update_one({"task_id": task_id, "user_id": user_id}, {"$set": {"status": "Completed"}})
        return jsonify({"message": "Proposal accepted successfully"}), 200
    else:
        return jsonify({"message": f"Proposal not found for user {user_id} and task {task_id}"}), 404

@app.route('/proposer/task-review/<string:task_id>', methods=['POST'], endpoint="task_review_proposer")
@newlogin_is_required
@is_onboarded
def task_review_proposer(user,task_id):
    form_data = request.get_json(force=True)
    user_id =  form_data.get("hirer_id")
    stars =  form_data.get("rating")
    message =  form_data.get("text")
    review={
        "task_id":task_id,
        "stars":stars,
        "message":message,
        "date":datetime.now()
    }
    user_details_collection.update_one({"user_id": user_id}, {"$push": {"hirer_reviews": review}})
    tasks_details_collection.update_one({"task_id": task_id}, {"$set": {"hirer_review": review}})
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id, "user_id": user.get("user_id")},{"_id": 0})
    print(proposal,'proposal')
    if proposal:
        chat_details = {
            "hirer_id": proposal.get("hirer_id"),
            "proposer_id": proposal.get("user_id"),
            "task_id": task_id,
            "sent_by": user.get("user_id"),
            "sent_on": datetime.now(),
            "msg": message,
            "rating":stars,
            "seen":False,
            "type":"review"
        }
        task_chat_details_collection.insert_one(chat_details)
        tasks_details_collection.update_one({"task_id": task_id, "user_id": user_id}, {"$set": {"status": "Completed"}})
        return jsonify({"message": "Proposal accepted successfully"}), 200
    else:
        return jsonify({"message": f"Proposal not found for user {user_id} and task {task_id}"}), 404

@app.route('/proposals/task/<string:task_id>', methods=['GET', 'POST'], endpoint="task_responses")
@newlogin_is_required
@is_onboarded
def task_responses(user,task_id):
    if task_details := tasks_details_collection.find_one({"task_id": task_id},{"_id": 0}):
        pageno = request.args.get("pageno")
        seen_count = task_seen_by_collection.count_documents({"task_id": task_id})
        task_details['seen_count']=seen_count
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(candidate_task_proposal_collection.find({"task_id": task_id})))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
            {
                "$match": {"task_id": task_id}
            },
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'candidate_details'
                }
            },
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            }, {
        # Add average rating field to user_details by calculating from proposer_reviews
        "$addFields": {
            "user_details": {
                "$map": {
                    "input": "$user_details",
                    "as": "user",
                    "in": {
                        "$mergeObjects": [
                            "$$user",
                            {
                                "average_review": {
                                    "$cond": {
                                        "if": { "$gt": [{ "$size": { "$ifNull": ["$$user.proposer_reviews", []] } }, 0] },
                                        "then": { 
                                            "$avg": "$$user.proposer_reviews.stars" 
                                        },
                                        "else": None  # Set to None if there are no reviews
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    },
           {
        '$project': {
            '_id': 0, 
            'user_details._id': 0,
            'candidate_details._id': 0,
        },
    },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
        ]
        all_responses = list(candidate_task_proposal_collection.aggregate(pipeline))
        return jsonify({"task_id":task_id, "all_responses":all_responses, "task_details":task_details, "total_pages":total_pages, "page_number":page_number})


@app.route('/proposalsSent', methods=['GET', 'POST'], endpoint="proposals")
@newlogin_is_required
@is_onboarded
def proposals(user):
    user_id=user.get('user_id')
    if proposals := candidate_task_proposal_collection.find({"user_id": user_id},{"_id": 0}):
        pageno = request.args.get("pageno")
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(candidate_task_proposal_collection.find({"user_id": user_id})))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
            {
                "$match": {"user_id": user_id}
            },
            {
                '$lookup': {
                    'from': 'tasks_details', 
                    'localField': 'task_id', 
                    'foreignField': 'task_id', 
                    'as': 'task_details'
                }
            },
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            },
           {
        '$project': {
            '_id': 0, 
            'user_details._id': 0,
            'candidate_details._id': 0,
        },
    },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
        ]
        proposals = list(candidate_task_proposal_collection.aggregate(pipeline))
        return jsonify({"proposals":proposals,"total_pages":total_pages, "page_number":page_number})

@app.route("/chats", methods=['GET'], endpoint='all_chats')
@newlogin_is_required
def all_chats(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    key = "hirer_id" if purpose == "hirer" else "jobseeker_id"
    localField = "hirer_id" if purpose == "jobseeker" else "jobseeker_id"
    localAs = "hirer_details" if purpose == "jobseeker" else "jobseeker_details"
    statusLocalAs = "hirer_details_status" if purpose == "jobseeker" else "jobseeker_details_status"
    pipeline = [
         {
                "$match": {key: user_id,"status": { "$ne": "closed" }}
            },
         {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': localField, 
                    'foreignField': 'user_id', 
                    'as': localAs
                }
            },
             {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': localField, 
                    'foreignField': 'user_id', 
                    'as': statusLocalAs
                }
            },
         {
                '$lookup': {
                    'from': 'jobs_details', 
                    'localField': "job_id", 
                    'foreignField': 'job_id', 
                    'as': "job_details"
                }
            },
         
        {"$lookup": {
            "from": "chat_details",
            "let": { "connection_hirer_id":"$hirer_id","connection_jobseeker_id":"$jobseeker_id","connection_job_id": "$job_id" },
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                #{"$ne":["$sent_by",purpose]},
                                  { "$eq": ["$job_id", "$$connection_job_id"] },
                                    { "$eq": ["$hirer_id", "$$connection_hirer_id"] },
                                    { "$eq": ["$jobseeker_id", "$$connection_jobseeker_id"] },
                                #{ "$eq": ["$seen", False] } 
                            ]
                        }
                    }
                },
                 { "$sort": { "sent_on": -1 } },  # Sort by `sent_on` in descending order
                    #{ "$group": {
                     #   "_id": None,
                     #   "last_unread_message": { "$first": "$$ROOT" },  # Take the most recent unread message
                     #   "unread_count": { "$sum": 1 }  # Count all unseen messages
                    #}},
                 #{ "$sort": { "sent_on": -1 } },  # Sort messages in descending order of sent_on
                    { "$group": {
                        "_id": None,
                        "all_messages": {
                            "$push": {
                                "msg": "$msg",
                                "sent_on": "$sent_on",
                                "seen": "$seen"
                            }
                        },  # Collect all messages with msg, sent_on, seen
                        "last_message": {
                            "$first": { "msg": "$msg", "sent_on": "$sent_on" }  # Get text and date of the last message
                        },
                        "unread_count":  {"$sum": {"$cond": [{"$and": [ { "$eq": ["$seen", False] }, { "$ne": ["$sent_by", purpose] }] },1,0 ]}}
                    }}
            ],
            "as": "unread_messages"
        },
         },
          {
            "$addFields": {
                  "last_unread_message": {
                    "$ifNull": [{ "$arrayElemAt": ["$unread_messages.last_unread_message", 0] }, None]
                },
                "last_message_date": {
                    "$ifNull":[{ "$arrayElemAt": ["$unread_messages.last_message.sent_on", 0] }, datetime.min]  # Set to sent_on of last unread message
                }
            },
        },
           {
        '$project': {
            '_id': 0, 
            f'{localAs}._id': 0,
            'job_details._id': 0,
        }
    },
      {
            "$sort": {
                "last_message_date": -1  # Sort by last unread message date in descending order
            }
        }
    ]
    all_connections = list(connection_details_collection.aggregate(pipeline))
    return jsonify({"purpose":purpose, "all_connections":all_connections})

@app.route("/task_chats", methods=['GET'], endpoint='all_task_chats')
@newlogin_is_required
def all_task_chats(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    key = "hirer_id" if user_id == "hirer" else "proposer_id"
    localField = "hirer_id" if purpose == "jobseeker" else "jobseeker_id"
    localAs = "hirer_details" if purpose == "jobseeker" else "jobseeker_details"
    pipeline = [
         {
                "$match": {
                      "$or": [
                          { "hirer_id": user_id },
                         { "proposer_id": user_id }
                            ]
                }
            },
         {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'hirer_id', 
                    'foreignField': 'user_id', 
                    'as': 'hirer_details'
                }
            },
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'proposer_id', 
                    'foreignField': 'user_id', 
                    'as': 'jobseeker_details'
                }
            },
         {
                '$lookup': {
                    'from': 'tasks_details', 
                    'localField': "task_id", 
                    'foreignField': 'task_id', 
                    'as': "task_details"
                }
            },
         
        {"$lookup": {
            "from": "task_chat_details",
            "let": { "connection_hirer_id":"$hirer_id","connection_jobseeker_id":"$jobseeker_id","connection_task_id": "$task_id" },
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                #{"$ne":["$sent_by",purpose]},
                                  { "$eq": ["$task_id", "$$connection_task_id"] },
                                    { "$eq": ["$hirer_id", "$$connection_hirer_id"] },
                                    { "$eq": ["$jobseeker_id", "$$connection_jobseeker_id"] },
                                #{ "$eq": ["$seen", False] } 
                            ]
                        }
                    }
                }, 
                 { "$sort": { "sent_on": -1 } },  # Sort by `sent_on` in descending order
                    #{ "$group": {
                     #   "_id": None,
                     #   "last_unread_message": { "$first": "$$ROOT" },  # Take the most recent unread message
                     #   "unread_count": { "$sum": 1 }  # Count all unseen messages
                    #}},
                 #{ "$sort": { "sent_on": -1 } },  # Sort messages in descending order of sent_on
                    { "$group": {
                        "_id": None,
                        "all_messages": {
                            "$push": {
                                "msg": "$msg",
                                "sent_on": "$sent_on",
                                "seen": "$seen"
                            }
                        },  # Collect all messages with msg, sent_on, seen
                        "last_message": {
                            "$first": { "msg": "$msg", "sent_on": "$sent_on" }  # Get text and date of the last message
                        },
                        "unread_count":  {"$sum": {"$cond": [{"$and": [ { "$eq": ["$seen", False] }, { "$ne": ["$sent_by",user_id ] }] },1,0 ]}}
                    }}
            ],
            "as": "unread_messages"
        },
         },
          {
            "$addFields": {
                  "last_unread_message": {
                    "$ifNull": [{ "$arrayElemAt": ["$unread_messages.last_unread_message", 0] }, None]
                },
                "last_message_date": {
                    "$ifNull":[{ "$arrayElemAt": ["$unread_messages.last_message.sent_on", 0] }, datetime.min]  # Set to sent_on of last unread message
                },
      "mytask": {
        "$cond": {
          "if": {
            "$or": [
              { "$eq": ["$hirer_id", user_id] }
            ]
          },
          "then": True,
          "else": False
        }
      }
            },
        },
           {
        '$project': {
            '_id': 0, 
            f'{localAs}._id': 0,
            'tasks_details._id': 0,
        }
    },
      {
            "$sort": {
                "last_message_date": -1  # Sort by last unread message date in descending order
            }
        }
    ]
    all_connections = list(connection_task_details_collection.aggregate(pipeline))
    return jsonify({"purpose":purpose, "all_connections":all_connections})

@app.route("/unread", methods=['GET'], endpoint='unread_chats')
@newlogin_is_required
def unread_chats(user):
    user_id = user.get("user_id")
    purpose = user.get("role")
    key = "hirer_id" if purpose == "hirer" else "jobseeker_id"
    count=connection_details_collection.count_documents({key:user_id})
    all_chats=list(chat_details_collection.find({"sent_by": {"$ne":purpose},key:user_id,'seen':False},{"_id": 0}))
    return jsonify({"purpose":purpose, "all_chats":all_chats,"count":count})


import time
@app.route("/chat/<string:incoming_user_id>/<string:job_id>", methods=['GET', 'POST'], endpoint='specific_chat')
@newlogin_is_required
def specific_chat(user,incoming_user_id, job_id):
    user_id = user.get("user_id")
    purpose = user.get("role")
    if request.method == 'POST':
        link=''
        file = request.files.get('file')
        mimetype=''
        subType=''
        if file:
           mimetype=file.mimetype
           extension=mimetype.split("/")[1]
           subType=mimetype.split("/")[0]
           id=str(uuid.uuid4())
           link=upload_file_firebase(file, f"{id}/.{extension}")
        data=dict(request.form)
        msg=data.get("msg")
        type=data.get("type")
        chat_details = {
            "hirer_id": user_id if purpose == "hirer" else incoming_user_id,
            "jobseeker_id": user_id if purpose == "jobseeker" else incoming_user_id,
            "job_id": job_id,
            "sent_by": purpose,
            "sent_on": datetime.now(),
            "msg": msg,
            "link":link,
            "type":type,
            "subType":subType,
            "seen":False
        }
        chat_data=chat_details
        chat_details_collection.insert_one(chat_details)
        channel_id = f"{user_id}_{incoming_user_id}_{job_id}" if purpose == "jobseeker" else f"{incoming_user_id}_{user_id}_{job_id}"
        chat_data["sent_on"]=datetime.now().isoformat()
        chat_data.pop("_id")
        print(chat_data,'chat_details',datetime.now().isoformat(),'inka')
        pusher_client.trigger(channel_id, purpose, json.dumps(chat_data))
        return {"status": "saved"}
    hirer_id = incoming_user_id if purpose == "jobseeker" else user_id
    jobseeker_id = user_id if purpose == "jobseeker" else incoming_user_id
    if onboarding_details := onboarding_details_collection.find_one({"user_id": incoming_user_id},{"_id": 0}):
        name = onboarding_details.get("company_name") if purpose == "jobseeker" else onboarding_details.get("candidate_name")
        incoming_user = user_details_collection.find_one({"user_id":incoming_user_id})
        print(incoming_user,'incoming user')
        pipeline = [
            {"$match": {"hirer_id": hirer_id, "jobseeker_id": jobseeker_id, "job_id": job_id}},
            {"$project": {"_id": 0}},
        ]
        chat_details_collection.update_many({"sent_by": {"$ne":purpose},"jobseeker_id":jobseeker_id, "hirer_id": hirer_id, "job_id": job_id},{"$set": {"seen": True}})
        all_chats = list(chat_details_collection.aggregate(pipeline))
        channel_id = f"{user_id}_{incoming_user_id}_{job_id}" if purpose == "jobseeker" else f"{incoming_user_id}_{user_id}_{job_id}"
        job_details = jobs_details_collection.find_one({"job_id": job_id},{"_id": 0,"job_title": 1})
        meet_details = {
            "meetLink": f"{url_}/meet/{channel_id}"
        }
        return jsonify({'incoming_user_id':incoming_user_id,"status":incoming_user.get("status"),"last_seen":incoming_user.get("last_seen"), 'purpose':purpose, 'all_chats':all_chats, 'name':name, 'channel_id':channel_id, 'job_id':job_id, 'job_details':job_details, 'meet_details':meet_details})
    else:
        abort(500, {"message": "User Not Found!"})

@app.route("/task_chat/<string:proposer_id>/<string:task_id>", methods=['GET', 'POST'], endpoint='specific_task_chat')
@newlogin_is_required
def specific_task_chat(user,proposer_id, task_id):
    user_id = user.get("user_id")
    purpose = user.get("role")
    #print(task_id,'task_id')
    task = tasks_details_collection.find_one({"task_id": task_id},{"_id": 0})
    #print(task,task_id,'taske')
    hirer_id=task.get("user_id")
    proposal = candidate_task_proposal_collection.find_one({"task_id": task_id,"user_id":proposer_id,"hirer_id":hirer_id},{"_id": 0})
    incoming_user_id=hirer_id if user_id==proposer_id else proposer_id
    link=''
    if request.method == 'POST':
        file = request.files.get('file')
        mimetype=file.mimetype
        subType=mimetype.split("/")[1]
        if file:
           file_id=str(uuid.uuid4())
           link=upload_file_firebase(file, f"{file_id}/.{subType}")
        dicte=dict(request.form)
        print(link,'deata')
        data = dicte
        msg=data.get("msg")
        type = data.get("type")
        subType = subType
        chat_details = {
            "hirer_id": hirer_id,
            "proposer_id": proposer_id,
            "task_id": task_id,
            "sent_by": user_id,
            "sent_on": datetime.now(),
            "msg": msg,
            "link":link,
            "seen":False,
            "type":type
        }
        task_chat_details_collection.insert_one(chat_details)
        channel_id = f"{hirer_id}_{proposer_id}_{task_id}" if purpose == "jobseeker" else f"{incoming_user_id}_{user_id}_{task_id}"
        #pusher_client.trigger(channel_id, purpose, {'msg': msg})
        return {"status": "saved"}
    if onboarding_details := onboarding_details_collection.find_one({"user_id": proposer_id},{"_id": 0}):
        name = onboarding_details.get("company_name") if purpose == "jobseeker" else onboarding_details.get("candidate_name")
        pipeline = [
            {"$match": {"hirer_id": hirer_id, "proposer_id": proposer_id, "task_id": task_id}},
            {"$project": {"_id": 0}},
        ]
        task_chat_details_collection.update_many({"sent_by": {"$ne":user_id},"proposer_id":proposer_id, "hirer_id": hirer_id, "task_id": task_id},{"$set": {"seen": True}})
        all_chats = list(task_chat_details_collection.aggregate(pipeline))
        channel_id = f"{user_id}_{incoming_user_id}_{task_id}" if purpose == "jobseeker" else f"{incoming_user_id}_{user_id}_{task_id}"
        task_details = tasks_details_collection.find_one({"task_id": task_id},{"_id": 0})
        meet_details = {
            "meetLink": f"{url_}/meet/{channel_id}"
        }
        return jsonify({'incoming_user_id':incoming_user_id, 'purpose':purpose, 'all_chats':all_chats,'proposal':proposal, 'name':name, 'channel_id':channel_id, 'task_id':task_id, 'task_details':task_details, 'meet_details':meet_details})
    else:
        abort(500, {"message": "User Not Found!"})

@app.route("/initiate_chat/<string:jobseeker_id>/<string:job_id>", methods =['GET'], endpoint="initiate_chat")
@newlogin_is_required
@is_hirer
def initiate_chat(user,jobseeker_id, job_id):
    user_id = user.get("user_id")
    if connection_details := connection_details_collection.find_one({"jobseeker_id": jobseeker_id, "hirer_id": user_id,"job_id":job_id},{"_id": 0}):
        pass
    else:
        if _ := candidate_job_application_collection.find_one({"user_id": jobseeker_id, "hirer_id": user_id, "job_id": job_id},{"_id": 0}):
            connection_details = {
            "created_on": datetime.now(),
            "hirer_id": user_id,
            "jobseeker_id": jobseeker_id,
            "job_id": job_id
            }
            connection_details_collection.insert_one(connection_details)
            candidate_job_application_collection.update_one({"user_id": jobseeker_id, "hirer_id": user_id, "job_id": job_id},{"$set": {"chat_initiated": True}})
        else:
            abort(500, {"message": "Either job_id or jobseeker_id is wrong!"})
    return jsonify({"message":"initiated"}),200

@app.route("/initiate_workstream/<string:proposer_id>/<string:task_id>", methods =['GET'], endpoint="initiate_workstream")
@newlogin_is_required
def initiate_workstream(user,proposer_id, task_id):
    user_id = user.get("user_id")
    print(user_id,proposer_id,'connectione')
    if connection_details := connection_task_details_collection.find_one({"proposer_id": proposer_id, "hirer_id": user_id,"task_id":task_id},{"_id": 0}):
        pass
    else:
        if _ := candidate_task_proposal_collection.find_one({"hirer_id":user_id, "user_id": proposer_id, "task_id": task_id},{"_id": 0}):
            connection_details = {
            "created_on": datetime.now(),
            "hirer_id": user_id,
            "proposer_id": proposer_id,
            "task_id": task_id
            }
            print('connection')
            connection_task_details_collection.insert_one(connection_details)
            proposal=candidate_task_proposal_collection.find_one_and_update({"hirer_id": user_id, "user_id": proposer_id, "task_id": task_id},{"$set": {"workstream_initiated": True}})
            print(proposal,'proposal')
            chat_details = {
            "hirer_id": user_id,
            "proposer_id": proposer_id,
            "task_id": task_id,
            "sent_by": proposer_id,
            "sent_on": datetime.now(),
            "msg": proposal.get("message"),
            "seen":False,
            "type":'proposal',
            "proposal":proposal
             }
            task_chat_details_collection.insert_one(chat_details)
        else:
            abort(500, {"message": "Either job_id or jobseeker_id is wrong!"})
    return jsonify({"message":"initiated"}),200

@app.route("/close_chat/<string:jobseeker_id>/<string:job_id>", methods =['GET'], endpoint="close_chat")
@newlogin_is_required
@is_hirer
def close_chat(user,jobseeker_id, job_id):
    user_id = user.get("user_id")
    if  connection_details_collection.find_one({"jobseeker_id": jobseeker_id, "hirer_id": user_id,"job_id":job_id},{"_id": 0}):
        connection_details_collection.update_one({"jobseeker_id": jobseeker_id, "hirer_id": user_id,"job_id":job_id},{"$set":{"status":"closed"}})
        return jsonify({"message":"chat closed"}),200
    else:
        return jsonify({"message":"chat close failed!"}),400

###### FAIZAN #####

#Function to get user by id    
def get_user_by_id(user_id):
    return user_details_collection.find_one({"user_id": user_id}, {"_id": 0,'password':0})
#Function to verify user token 
def verify_token(token):
    try:
        decoded = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return decoded.get('public_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

#Route to verify token
@app.route("/verify-token", methods=['POST'])
def verify_token_route():
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({"valid": False, "message": "No token provided"}), 400
    # Token with "Bearer " prefix
    token = auth_header.split(" ")[1] 
    user_id = verify_token(token)
    
    if user_id:
        user = get_user_by_id(user_id) 
        if user:
            return jsonify({"valid": True, "user": user}), 200
        else:
            return jsonify({"valid": False, "message": "User not found"}), 404
    else:
        return jsonify({"valid": False, "message": "Invalid token"}), 401 

@app.route("/meet/<string:channel_id>", methods=['GET'], endpoint='meeting')
def meeting(channel_id):
    purpose = request.args.get("purpose")
    candidate_id, hirer_id, job_id = channel_id.split("_")
    hirer_pipeline = [
           {
                "$match": {"user_id": hirer_id}
            },
         {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': "user_id", 
                    'foreignField': 'user_id', 
                    'as': "user_details"
                }
            }
    ]
    candidate_pipeline = [
           {
                "$match": {"user_id": candidate_id}
            },
         {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': "user_id", 
                    'foreignField': 'user_id', 
                    'as': "user_details"
                }
            }
    ]
    if onboarding_details := list(onboarding_details_collection.aggregate(hirer_pipeline)):
        company_name = onboarding_details[0].get("company_name")
        hirer_email = onboarding_details[0].get("user_details")[0]['email']
    else:
        abort(500, {"message": "Invalid Channel ID"})
    if onboarding_details := list(onboarding_details_collection.aggregate(candidate_pipeline)):
        candidate_name = onboarding_details[0].get("candidate_name")
        candidate_email = onboarding_details[0].get("user_details")[0]['email']
    else:
        abort(500, {"message": "Invalid Channel ID"})
    if job_details := jobs_details_collection.find_one({"job_id": job_id}, {"_id": 0, "job_title": 1}):
        if purpose == "hirer":
                jwt = create_jwt(company_name, hirer_email, True)
        else:
                jwt = create_jwt(candidate_name, candidate_email, False)
        meet_details = {
            "roomName": f"vpaas-magic-cookie-06dfe06f9743475abdab4c2e451d3894/{channel_id}",
            "jwt": jwt,
            "meetLink": f"http:127.0.0.1:5000/meet/{channel_id}"
        }
        return render_template('videoservice/main.html', meet_details=meet_details,jwt=jwt, job_details=job_details, onboarding_details=onboarding_details)
    else:
        abort(500, {"message": "Invalid Channel ID"})


@app.route('/hirer/view/job/<string:job_id>', methods=['GET'], endpoint="view_job")
@newlogin_is_required
@is_hirer
def view_job(user,job_id):
    user_id = user.get("user_id")
    if job_details_cursor := jobs_details_collection.find_one({"user_id": str(user_id), "job_id": str(job_id)},{"_id": 0}):
        job_details = job_details_cursor
        return jsonify({'job_details':job_details})
    else:
        abort(404, {"message": "Job not found"})

@app.route('/hirer/view/jobs', methods=['GET'], endpoint="view_jobs")
@newlogin_is_required
@is_hirer
def view_jobs(user):
    user_id = user.get("user_id")
    jobs_details_cursor = jobs_details_collection.find({"user_id": str(user_id)}, {"_id": 0})
    jobs_details = list(jobs_details_cursor)
    if jobs_details:
        return jsonify({'jobs_details': jobs_details})
    else:
        abort(404, {"message": "Jobs not found"})

@app.route('/hirer/view/jobs', methods=['GET'], endpoint="view__jobs")
@newlogin_is_required
@is_candidate
def view__jobs(user):
    user_id = user.get("user_id")
    jobs_details_cursor = jobs_details_collection.find({"user_id": str(user_id)}, {"_id": 0})
    
    jobs_details = list(jobs_details_cursor)
    
    if jobs_details:
        return jsonify({'jobs_details': jobs_details})
    else:
        abort(404, {"message": "Jobs not found"})

@app.route("/filterJobs", methods=['GET'], endpoint="filter__jobs")
@newlogin_is_required
def filter_jobs(user):
    user_id=user.get('user_id')
    searched_for = request.args.get("search")
    job_title = request.args.get("job_title")
    experience_level = request.args.get("experience_level")
    job_topics = request.args.get("job_topics")
    salary_range = request.args.get("salary_range")
    mode_of_work = request.args.get("mode_of_work")
    job_location = request.args.get("job_location")
    job_type = request.args.get("job_type")
    job_posted=request.args.get("job_posted")
    job_category=request.args.get("job_category")
    salary_from=request.args.get("salary_from")
    salary_to=request.args.get("salary_to")
    query = {}
    resume_skills = get_resume_skills(user_id)
    regex= create_skills_regex_pattern(resume_skills)
    # Fetch all jobs matching the user's skills
    regex_pattern=regex
    if job_title:
        query['job_title'] = {"$regex": job_title, "$options": "i"}
    if experience_level:
        query['experience_level'] = experience_level
    if salary_range:
        query['salary_range'] = salary_range
    if job_type:
        query['job_type'] = job_type
    if mode_of_work:
        query['mode_of_work'] = mode_of_work
    if job_location:
        query['job_location'] = job_location
    if job_posted:
        query['created_on'] = job_posted
    if job_category:
        query['job_category'] = job_category
    if job_topics:
        # Remove '#' if present and create a regex pattern
        topics = [topic.strip('#') for topic in job_topics.split()]
        topics_regex = '|'.join(topics)
        query['job_topics'] = {"$regex": topics_regex, "$options": "i"}
    if job_posted:
       start = datetime.now()-timedelta(days=int(job_posted))
       end = datetime.now()
       query['created_on'] = {"$gte":start,"$lt":end}
    #if salary_from:
     #   query['salary_from'] = {"$gte":int(0)}
    if salary_from:
        query['salary_from'] = {"$gte":int(salary_from)}

    pipeline = [
        {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
            {
            '$lookup': {
                'from': 'profile_details', 
                'localField': 'user_id', 
                'foreignField': 'user_id', 
                'as': 'onboarding_details'
            }
        }, 
        {
                '$lookup': {
                    'from': 'saved_jobs', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'saved_jobs_details'
                }
            }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        }
    ]
    if searched_for:
        pipeline.append({
            "$match": {
                "$or": [
                    {"job_title": {"$regex": searched_for, "$options": "i"}},
                    {"job_description": {"$regex": searched_for, "$options": "i"}},
                    {"job_type": {"$regex": searched_for, "$options": "i"}},
                    {"job_topics": {"$regex": searched_for, "$options": "i"}},
                    {"job_category": {"$regex": searched_for, "$options": "i"}},
                    {"onboarding_details.company_name": {"$regex": searched_for, "$options": "i"}}
                ]
            }
        })

    if not searched_for:
       print('not query')
       query['$or'] = [
        {'job_title': {'$regex': regex_pattern, '$options': 'i'}},
        {'job_description': {'$regex': regex_pattern, '$options': 'i'}},
        {'job_topics': {'$regex': regex_pattern, '$options': 'i'}},
    ]

    if query:
        pipeline.append({"$match": query})

    # Add the lookup and project stages
    pipeline.extend([
        {
            '$lookup': {
                'from': 'jobs_details',
                'localField': 'job_id',
                'foreignField': 'job_id',
                'as': 'job_details'
            }
        },
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        }
    ])
    all_jobs = list(jobs_details_collection.aggregate(pipeline))
    all_updated_jobs = []
    for idx, job in enumerate(all_jobs):
            if applied := candidate_job_application_collection.find_one({"job_id": job.get("job_id"),"user_id": user_id},{"_id": 0}):
                pass
            else:
                all_updated_jobs.append(job)
    if(len(list(all_updated_jobs))==0):
        print('zero jobs')
        if(not searched_for):
            all_jobs=list(jobs_details_collection.aggregate([{
            "$match": {"status":"published"}},{
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
            {
            '$lookup': {
                'from': 'profile_details', 
                'localField': 'user_id', 
                'foreignField': 'user_id', 
                'as': 'onboarding_details'
            }
        }, 
        {
                '$lookup': {
                    'from': 'saved_jobs', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'saved_jobs_details'
                }
            }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        }]))
            for idx, job in enumerate(all_jobs):
             if applied := candidate_job_application_collection.find_one({"job_id": job.get("job_id"),"user_id": user_id},{"_id": 0}):
                pass
             else:
                all_updated_jobs.append(job)
    return jsonify({'all_jobs': all_updated_jobs})

@app.route("/ufilterJobs", methods=['GET'], endpoint="ufilter__jobs")
def ufilter_jobs():
    searched_for = request.args.get("search")
    job_title = request.args.get("job_title")
    experience_level = request.args.get("experience_level")
    job_topics = request.args.get("job_topics")
    salary_range = request.args.get("salary_range")
    mode_of_work = request.args.get("mode_of_work")
    job_location = request.args.get("job_location")
    job_type = request.args.get("job_type")
    job_posted=request.args.get("job_posted")
    job_category=request.args.get("job_category")
    salary_from=request.args.get("salary_from")
    salary_to=request.args.get("salary_to")
    print(request.args,'args')
    query = {}
    if job_title:
        query['job_title'] = {"$regex": job_title, "$options": "i"}
    if experience_level:
        query['experience_level'] = experience_level
    if salary_range:
        query['salary_range'] = salary_range
    if job_type:
        query['job_type'] = job_type
    if mode_of_work:
        query['mode_of_work'] = mode_of_work
    if job_location:
        query['job_location'] = job_location
    if job_posted:
        query['created_on'] = job_posted
    if job_category:
        query['job_category'] = job_category
    if job_topics:
        # Remove '#' if present and create a regex pattern
        topics = [topic.strip('#') for topic in job_topics.split()]
        topics_regex = '|'.join(topics)
        query['job_topics'] = {"$regex": topics_regex, "$options": "i"}
    print(salary_from,'when')
    if job_posted:
       start = datetime.now()-timedelta(days=int(job_posted))
       end = datetime.now()
       query['created_on'] = {"$gte":start,"$lt":end}
    if salary_from:
        query['salary_from'] = {"$gte":int(salary_from)}
    if salary_to:
        query['salary_to'] = {"$lt":int(salary_to)}
    pipeline = [
        {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
         {
            '$lookup': {
                'from': 'profile_details', 
                'localField': 'user_id', 
                'foreignField': 'user_id', 
                'as': 'onboarding_details'
            }
        }, 
        {
                '$lookup': {
                    'from': 'saved_jobs', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'saved_jobs_details'
                }
            }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        }
    ]
    if searched_for:
        pipeline.append({
            "$match": {
                "$or": [
                    {"job_title": {"$regex": searched_for, "$options": "i"}},
                    {"job_description": {"$regex": searched_for, "$options": "i"}},
                    {"job_type": {"$regex": searched_for, "$options": "i"}},
                    {"job_topics": {"$regex": searched_for, "$options": "i"}},
                    {"job_category": {"$regex": searched_for, "$options": "i"}}
                ],
            }
        })
    if query:
        pipeline.append({"$match": query})

    # Add the lookup and project stages
    pipeline.extend([
        {
            '$lookup': {
                'from': 'jobs_details',
                'localField': 'job_id',
                'foreignField': 'job_id',
                'as': 'job_details'
            }
        },
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        }
    ])
    all_jobs = list(jobs_details_collection.aggregate(pipeline))
    return jsonify({'all_jobs': all_jobs})

@app.route("/jobs/tags", methods=['GET'])
def get_most_used_tags():
    limit = int(request.args.get("limit", 10))  # Default to top 10 if not specified
    pipeline = [
        {
            "$project": {
                "topics": {
                    "$split": [
                        "$job_topics",
                        " "
                    ]
                }
            }
        },
        {
            "$unwind": "$topics"
        },
        {
            "$group": {
                "_id": "$topics",
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"count": -1}
        },
        {
            "$limit": limit
        }
    ]

    result = list(jobs_details_collection.aggregate(pipeline))

    # Clean up tags (remove '#' if present) and format the result
    top_tags = [
        {
            "tag": re.sub(r'^#', '', item["_id"]),
            "count": item["count"]
        }
        for item in result if item["_id"].strip() 
    ]

    return jsonify({"top_tags": top_tags})

@app.route("/tasks/tags", methods=['GET'])
def get_most_used_job_tags(): 
    limit = int(request.args.get("limit", 10))  # Default to top 10 if not specified

    pipeline = [
        {
            "$project": {
                "topics": {
                    "$split": [
                        "$task_topics",
                        " "
                    ]
                }
            }
        },
        {
            "$unwind": "$topics"
        },
        {
            "$group": {
                "_id": "$topics",
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {"count": -1}
        },
        {
            "$limit": limit
        }
    ]

    result = list(tasks_details_collection.aggregate(pipeline))

    # Clean up tags (remove '#' if present) and format the result
    top_tags = [
        {
            "tag": re.sub(r'^#', '', item["_id"]),
            "count": item["count"]
        }
        for item in result if item["_id"].strip() 
    ]

    return jsonify({"top_tags": top_tags})


# pipeline = [
#     {
#         '$lookup': {
#             'from': 'jobs_details', 
#             'localField': 'job_id', 
#             'foreignField': 'job_id', 
#             'as': 'job_details'
#         }
#     }, 
#     {
#         '$project': {
#             '_id': 0,
#             'job_details._id': 0
#         }
#     }
# ]

@app.route('/create_order', methods=['POST'])
def create_order():
    data = request.get_json()

    amount = int(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    # Create Razorpay order
    order = razorpay_client.order.create(dict(
        amount=amount * 100,  # Amount in paise (multiply by 100)
        currency="INR",
        payment_capture="1"  # 1 means automatic payment capture
    ))

    return jsonify({
        'order_id': order['id'],
        'currency': order['currency'],
        'amount': order['amount']
    })

@app.route('/api/save-bank-details', methods=['POST'], endpoint="save_bank_details")
@newlogin_is_required
def save_bank_details(user):
    # Extract the bank details from the request
    data = request.get_json()
    user_id = user.get('user_id')
    bank_name = data.get('bankName')
    account_number = data.get('accountNumber')
    ifsc_code = data.get('ifscCode')
    bank_address = data.get('bankAddress')
    
    # Basic validation
    if not user_id or not bank_name or not account_number or not ifsc_code or not bank_address:
        return jsonify({"message": "All fields are required."}), 400

    # You can add more validations here (e.g., validating account number format, IFSC code format)
    
    # Create the bank details document
    bank_details = {
        "user_id": user_id,
        "bank_name": bank_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "bank_address": bank_address
    }

    try:
        # Insert the bank details into MongoDB
        user_details_collection.update_one({"user_id":user_id},{"$set":{'bank_details':bank_details}})
        return jsonify({"message": "Bank details saved successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error saving bank details", "error": str(e)}), 500

@app.route('/api/delete-bank-details', methods=['GET'], endpoint="delete_bank_details")
@newlogin_is_required
def delete_bank_details(user):
    user_id = user.get('user_id')
    # Create the bank details document

    try:
        # Insert the bank details into MongoDB
        user_details_collection.update_one({"user_id":user_id},{"$set":{'bank_details':''}})
        return jsonify({"message": "Bank details saved successfully!"}), 200
    except Exception as e:
        return jsonify({"message": "Error saving bank details", "error": str(e)}), 500

@app.route('/user/online', methods=['POST'],endpoint='mark_online')
@newlogin_is_required
def mark_online(user):
    """Mark a user as online and notify clients."""
    user_id = user.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    # Update user's status in the database
    user_details_collection.update_one(
        {"user_id": user_id},
        {"$set": {"status": "online", "last_seen": datetime.now()}},
        upsert=True
    )

    # Notify via Pusher
    pusher_client.trigger(
        'user-status-channel',
        'status-changed',
        {'user_id': user_id, 'status': 'online'}
    )

    return jsonify({"message": f"User {user_id} marked as online"}), 200

@app.route('/user/offline', methods=['POST'],endpoint='mark_offline')
@newlogin_is_required
def mark_offline(user):
    """Mark a user as offline and notify clients."""
    user_id = user.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    # Update user's status in the database
    user_details_collection.update_one(
        {"user_id": user_id},
        {"$set": {"status": "offline", "last_seen": datetime.now()}}
    )
    # Notify via Pusher
    pusher_client.trigger(
        'user-status-channel',
        'status-changed',
        {'user_id': user_id, 'status': 'offline'}
    )

    return jsonify({"message": f"User {user_id} marked as offline"}), 200

@app.route('/users/typing', methods=['POST'],endpoint='user_typing')
@newlogin_is_required
def user_typing(user):
    """
    Notify that a user is typing.
    """
    user_id=user.get("user_id")
    purpose=user.get("role")
    incoming_user_id = request.json.get('incoming_user_id')
    job_id = request.json.get('job_id')
    is_typing = request.json.get('is_typing')  # True or False
    channel_id= f"{user_id}_{incoming_user_id}_{job_id}" if purpose == "jobseeker" else f"{incoming_user_id}_{user_id}_{job_id}"
    print(channel_id,'channel_id',user,purpose)
    if not user_id or not channel_id or is_typing is None:
        return jsonify({"error": "Invalid payload"}), 400

    # Broadcast typing status via Pusher
    pusher_client.trigger(
        channel_id,
        "typing",
        {
            "user_id": user_id,
            "is_typing": is_typing,
        }
    )
    return jsonify({"message": "Typing status broadcasted"}), 200

@app.route('/plans', methods=['GET'])
def get_plans():
    """
    Fetch all available subscription plans.
    """
    all_plans = list(plans_collection.find({}, {"_id": 1, "name": 1, "price": 1, "features": 1}))
    return jsonify(all_plans), 200

@app.route('/upgrade', methods=['POST'])
def upgrade_plan():
    """
    Upgrade a hirer's subscription plan.
    """
    user_id = request.json.get('user_id')
    plan_id = request.json.get('plan_id')

    if not user_id or not plan_id:
        return jsonify({"error": "User ID and Plan ID are required"}), 400

    # Verify the plan exists
    plan = plans_collection.find_one({"_id": plan_id})
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    # Update the user's subscription
    user_details_collection.update_one(
        {"user_id": user_id},
        {"$set": {"subscription": plan_id, "job_limit": plan["job_limit"]}},
        upsert=True
    )

    return jsonify({"message": f"User {user_id} upgraded to {plan['name']} plan"}), 200

@app.route('/user/<user_id>', methods=['GET'])
def get_user_subscription(user_id):
    """
    Fetch the user's subscription plan details.
    """
    user = user_details_collection.find_one({"user_id": user_id}, {"_id": 0})
    plans=list(plans_collection.find({}))
    print(plans,user,'plan')
    plan = plans_collection.find_one({"_id":user.get("subscription")})
    jobs=jobs_details_collection.find({"user_id":user_id})
    jobscount=len(list(jobs))
    if jobscount>0:
       plan["job_count"]=len(list(jobs))
    else:
        plan["job_count"]=0
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user":user,"plan":plan}), 200

@app.route('/notifications', methods=['GET'],endpoint='get_notifications')
@newlogin_is_required
def get_notifications(user):
    # Retrieve query parameters
    user_id=user.get("user_id")
    notification_type = request.args.get('type')  # e.g., "job_recommendation"
    is_read = request.args.get('is_read')        # e.g., "true" or "false"
    start_date = request.args.get('start_date')  # e.g., "2024-11-01"
    end_date = request.args.get('end_date')      # e.g., "2024-11-23"

    query = {"user_id": user_id}
    if notification_type:
        query["type"] = notification_type
    if is_read is not None:
        query["is_read"] = is_read.lower() == "true"
    if start_date:
        query["created_at"] = {"$gte": datetime.fromisoformat(start_date)}
    if end_date:
        query["created_at"] = query.get("created_at", {})
        query["created_at"]["$lte"] = datetime.fromisoformat(end_date)

    notifications = list(notification_collection.find(query).sort("created_at", -1))
    for notification in notifications:
        notification["_id"] = str(notification["_id"])  # Convert ObjectId to string
    return jsonify({"notifications":notifications}), 200

@app.route('/hirer-notifications', methods=['GET'],endpoint='get_hirer_notifications')
@newlogin_is_required
def get_hirer_notifications(user):
    # Retrieve query parameters
    user_id=user.get("user_id")
    notification_type = request.args.get('type')  # e.g., "job_recommendation"
    is_read = request.args.get('is_read')        # e.g., "true" or "false"
    start_date = request.args.get('start_date')  # e.g., "2024-11-01"
    end_date = request.args.get('end_date')      # e.g., "2024-11-23"

    query = {"user_id": user_id}
    if notification_type:
        query["type"] = notification_type
    if is_read is not None:
        query["is_read"] = is_read.lower() == "true"
    if start_date:
        query["created_at"] = {"$gte": datetime.fromisoformat(start_date)}
    if end_date:
        query["created_at"] = query.get("created_at", {})
        query["created_at"]["$lte"] = datetime.fromisoformat(end_date)

    notifications = list(notification_collection.find(query).sort("updated_at", -1))
    for notification in notifications:
        notification["_id"] = str(notification["_id"])  # Convert ObjectId to string
    return jsonify({"notifications":notifications}), 200

@app.route('/new-notifications', methods=['GET'],endpoint='new_notifications')
@newlogin_is_required
def new_notifications(user):
    # Retrieve query parameters
    user_id=user.get("user_id")
    notifications = list(notification_collection.find({"is_new":True,"user_id":user_id}).sort("created_at", -1))
    for notification in notifications:
        notification["_id"] = str(notification["_id"])  # Convert ObjectId to string
    return jsonify({"notifications":notifications}), 200

@app.route('/markasread-notifications', methods=['GET'],endpoint='read_notifications')
@newlogin_is_required
def read_notifications(user):
    # Retrieve query parameters
    user_id=user.get("user_id")
    notification_collection.update_many({"is_new":True,"user_id":user_id},{"$set":{"is_new":False}})
    return jsonify({"notifications":"marked as read"}), 200

def addplans():
    allplans=[
    {
      "_id":"basic",
      "features": [
        "Post up to 5 jobs"
      ], 
      "job_limit": 5, 
      "name": "Basic Plan", 
      "price": 0
    }, 
    {
      "_id":"premium",
      "features": [
        "Post up to 20 jobs", 
        "Priority support"
      ], 
      "job_limit": 20, 
      "name": "Premium Plan", 
      "price": 50
    }, 
    {
      "_id":"enterprise",
      "features": [
        "Post up to 50 jobs", 
        "Dedicated account manager", 
        "Custom support"
      ], 
      "job_limit": 50, 
      "name": "Enterprise Plan", 
      "price": 100
    }
  ]
    #plans_collection.delete_many({})
    #plans_collection.insert_many(allplans)

addplans()