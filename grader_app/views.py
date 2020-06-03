from django.shortcuts import render, redirect
from .models import Essay, Assignment
from .forms import EssayForm, LoginForm, RegisterForm, SetupForm, InfoForm, ChangeForm, TeacherForm, AssignmentForm
from django.contrib.auth.decorators import login_required
from requests_oauthlib import OAuth2Session
from .models import User
from django.contrib import auth
from grammarbot import GrammarBotClient
from django.db.models import Q
from django.db import models
from operator import attrgetter
from django import forms
import json
from .tasks import grade_essay


# Create your views here.

def login(request):
    admins = {"2023avasanth", "2023pbhandar", "2023kbhargav"}

    if request.user.is_authenticated:
        return redirect("home")

    context = {
        'url': 'login'
    }

    CODE = None
    CLIENT_ID = "FeZBHle5SNytiEwAh333mPmoEmfFDQSF1Jigy2bW"
    CLIENT_SECRET = "saNPOvrrCGhNK1TywLjTsKo3M5uFzfQEgUtTpvvZsNIQPB75eeWYqhBxYMZJb0lKG5LZRZx1ZVN7ZUEiUUUqPeE8GMH0ZwdhbG4yNKKYmcCDu0UXV2gopeUB3B4cAIzw"
    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            if User.objects.filter(email=email).exists():
                user = auth.authenticate(email=email, password=form.cleaned_data["password"])
                if user is not None:
                    auth.login(request, user)
                    return redirect("http://localhost:8000/home")
            else:
                form = LoginForm()
                context['form'] = form

            context['error'] = "Username or Password is incorrect"

        else:
            form = LoginForm()
            context['form'] = form


    else:
        oauth = OAuth2Session(CLIENT_ID,
                              redirect_uri="http://localhost:8000/login",
                              scope=["read"])
        authorization_url, state = oauth.authorization_url("https://ion.tjhsst.edu/oauth/authorize/")
        context['url'] = authorization_url
        if "code" in request.GET:
            CODE = request.GET.get("code")

            token = oauth.fetch_token("https://ion.tjhsst.edu/oauth/token/",
                                      code=CODE,
                                      client_secret=CLIENT_SECRET)

            try:
                raw_profile = oauth.get("https://ion.tjhsst.edu/api/profile")
                profile = json.loads(raw_profile.content.decode())
                email = profile["tj_email"]
                if User.objects.filter(email=email).exists():
                    user = auth.authenticate(email=email,
                                             password=profile.get("ion_username") + profile.get("user_type"))
                    if user is not None:
                        auth.login(request, user)
                        user = request.user
                        user.logged_with_ion = True
                        user.save()
                        return redirect("http://localhost:8000/home")

                else:
                    if profile.get("ion_username") in admins or profile.get("is_eighth_admin"):
                        new_user = User.objects.create_superuser(email=email,
                                                                 password=profile.get("ion_username") + profile.get(
                                                                     "user_type"))
                    elif profile.get("is_teacher"):
                        new_user = User.objects.create_teacheruser(email=email,
                                                                   password=profile.get("ion_username") + profile.get(
                                                                       "user_type"))
                    else:
                        new_user = User.objects.create_studentuser(email=email,
                                                                   password=profile.get("ion_username") + profile.get(
                                                                       "user_type"))
                    new_user.logged_with_ion = True
                    new_user.first_name = profile.get("first_name")
                    new_user.middle_name = profile.get("middle_name")
                    new_user.last_name = profile.get("last_name")
                    new_user.year_in_school = profile.get("grade").get("name").upper()[:3]
                    a = Assignment(assignment_description="-------------", assignment_name="-------------")
                    a.save()
                    new_user.assignments.add(a)
                    new_user.save()
                    user = auth.authenticate(email=email,
                                             password=profile.get("ion_username") + profile.get("user_type"))
                    auth.login(request, user)
                    return redirect("http://localhost:8000/home")

            except Exception as e:
                args = {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
                token = oauth.refresh_token("https://ion.tjhsst.edu/oauth/token/", **args)
    return render(request, "login.html", context)


def logout(request):
    auth.logout(request)
    return redirect("home")
    '''
def create(request):    
    if request.user.is_authenticated:
        return redirect("home")
    context = {"method" : request.method}
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            error = False
            try:
                email = form.cleaned_data.get('email')
                qs = User.objects.filter(email=email)
                if qs.exists():
                    raise forms.ValidationError("email is taken")
            except forms.ValidationError:
                context['Error1'] = "Email is already taken"
                error = True
                
            try:
                password = form.clean_password2()
                if len(password) < 8:
                    raise ValueError
            except forms.ValidationError:
                context['Error2'] = "Passwords do no match"
                error = True
            except ValueError:
                context['Error2'] = "Passwords need to be at least 8 characters"
                error = True
                
            if not error:
                new_user = User.objects.create_studentuser(email=email, password=password)
                a = Assignment(assignment_description="-------------", assignment_name="-------------")
                a.save()
                new_user.assignments.add(a)
                new_user.save()

                user = auth.authenticate(email=email, password=password)
                auth.login(request, user)
                return redirect("http://localhost:8000/setup")
            else:
                form = RegisterForm()
                context['form'] = form
        else:
            form = RegisterForm()
            context['form'] = form
                
    else:
        form = RegisterForm()
        context['form'] = form
    return render(request, "create.html", context)
            
def setup(request) :
    context = {
        "method" : request.method,
        "form" : SetupForm()
    }
    if context['method'] == "POST":
        form = SetupForm(request.POST)
        if form.is_valid():
            user = request.user
            user.first_name = form.cleaned_data.get('first_name')
            user.middle_name = form.cleaned_data.get('middle_name')
            user.last_name = form.cleaned_data.get('last_name')
            user.year_in_school = form.cleaned_data.get('year_in_school')
            user.save()
            return redirect("home")
    return render(request, "setup.html", context) '''


def index(request):
    essays = []
    query = ""

    if request.GET:
        query = request.GET.get('q', 'Search for an essay')

    if query != "":
        profile = request.user
        queryset = []
        queries = query.split(" ")

        for q in queries:
            essays = Essay.objects.filter(
                Q(title__icontains=q) |
                Q(body__icontains=q)
            ).order_by('-created_on').distinct()

            for essay in essays:
                queryset.append(essay)

        essays = list(set(queryset))

    if request.user.is_authenticated and request.user.teacher and not request.user.admin:
        return redirect("teacher")

    if request.user.is_authenticated and essays == []:
        essays = Essay.objects.all().order_by('-created_on')

    context = {
        "essays": essays,
        "query": str(query),
        "search": query != ""
    }

    return render(request, "index.html", context)


@login_required(login_url="login")
def submit(request):
    context = {}
    form = EssayForm(request.POST or None, **{'user' : request.user})
    if request.method == 'POST':
        print("\n\n\n\n\n\n",request.POST,"\n\n\n")
        if form.is_valid():
            essay = Essay(
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                author=request.user,
                assignment=form.cleaned_data["assignment"],
                teacher=User.objects.get(email=form.cleaned_data["teachers"]),
                citation_type=form.cleaned_data["citation_type"]
            )
            essay.save()
            return redirect("home")
    context = {
        'form': form,
    }
    return render(request, "submit.html", context)


def load_assignments(request):
    teacher = request.GET.get('teacher')
    if "------------------------------------" != teacher:
        assigns = User.objects.get(email=teacher).assignments.all()

    else:
        assigns = "<option value="">------------------------------------</option>"
    return render(request, 'submit_options.html', {'assignments': assigns})


@login_required(login_url="login")
def detail(request, pk):
    essay = Essay.objects.get(pk=pk)
    context = {
        'essay': essay
    }

    return render(request, "detail.html", context)


@login_required(login_url="login")
def teacher(request):
    user = request.user

    if not user.teacher:
        return redirect("http://localhost:8000/home")

    query = ""

    if request.GET:
        query = request.GET.get("q", "")
        queryset = []
        queries = query.split(" ")

        for q in queries:
            essays = Essay.objects.filter(teacher=user.email).filter(
                Q(title__icontains=q) |
                Q(body__icontains=q)
            ).order_by('-created_on').distinct()

            for essay in essays:
                queryset.append(essay)

        essays = list(set(queryset))

    else:
        try:
            essays = Essay.objects.all().filter(teacher=user.email).order_by('-created_on')
        except Essay.DoesNotExist:
            essays = []

    context = {
        'essays': essays,
        'name': user.get_full_name(),
        "search": query != ""
    }
    return render(request, "teacher.html", context)


@login_required(login_url="login")
def grade(request):  # max 7973 characters/request, <100 requests/day

    if not request.user.teacher:
        return redirect("home")

    if request.GET:
        query = request.GET.get("q", "")
        queryset = []

        essays = Essay.objects.filter(teacher=request.user.email).filter(
            Q(assignment__icontains=query)
        ).order_by('-created_on').distinct()
        for essay in essays:
            # send celery worker to grade the essay
            grade_essay.delay(essay.id)

        context = {
            'essays': essays
        }

        return render(request, "grade.html", context)

    essays = []

    for essay in Essay.objects.filter(teacher=request.user.email):
        if essay.marked_body != "":
            print(essay.marked_body)
            essays.append(essay)

    context = {
        'essays': essays
    }

    return render(request, "grade.html", context)


def reformat(body):
    temp = body.split("\r\n")
    tempText = "<p>"

    for paragraph in temp:
        tempText += paragraph + "</p><p>"

    temp = tempText.split("\t")
    tempText = "&emsp;"

    for tab in temp:
        tempText += tab + "&emsp;"

    temp = ""
    for word in tempText.split(" "):
        if len(word) <= 4:
            temp += word + " "
        elif word[0:2] == "**":
            temp += "<mark style=\"background-color:yellow;\"><b>" + word[2:len(word) - 2] + "</b></mark> "
        else:
            temp += word + " "

    return temp + "</p>"


@login_required(login_url="login")
def teacher_detail(request, pk):
    user = request.user

    if not user.teacher:
        redirect("home")

    try:
        essay = Essay.objects.get(pk=pk)
    except Essay.DoesNotExist:
        essay = {}

    context = {
        'essay': essay,
    }
    return render(request, "teacher_detail.html", context)


@login_required(login_url="login")
def settings_changeInfo(request):
    profile = request.user

    context = {
        'error': "Cannot change info due to Ion login"
    }
    if request.method == 'POST':
        form = InfoForm(request.POST)

        if form.is_valid():
            profile.email = form.cleaned_data.get('email')
            profile.first_name = form.cleaned_data.get('first_name')
            profile.middle_name = form.cleaned_data.get('middle_name')
            profile.last_name = form.cleaned_data.get('last_name')
        profile.save()

    form = InfoForm(
        initial={'email': profile.email, 'first_name': profile.first_name, 'middle_name': profile.middle_name,
                 'last_name': profile.last_name})

    if profile.logged_with_ion:
        form.disable()
    context['form'] = form

    return render(request, "settings_info.html", context)


@login_required(login_url="login")
def settings_changePassword(request):
    profile = request.user

    context = {
        'error':"Cannot change password due to Ion login"
    }

    if request.method == 'POST':
        form = InfoForm(request.POST)

        if form.is_valid():
            password1 = form.cleaned_data.get('password_1')
            password2 = form.cleaned_data.get('password_2')
            if password1 != password2:
                context['error'] = "Passwords do not match"
            else:
                profile.set_password()

    form = ChangeForm()

    if profile.logged_with_ion:
        form.disable()
    context['form'] = form

    return render(request, "settings_password.html", context)


@login_required(login_url="login")
def settings_changeTeachers(request):
    profile = request.user
    context = {}

    names = [
        "period_1_teacher",
        "period_2_teacher",
        "period_3_teacher",
        "period_4_teacher",
        "period_5_teacher",
        "period_6_teacher",
        "period_7_teacher",
    ]

    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            teachers = {}
            error = False
            for name in names:
                teachers[name] = form.cleaned_data.get(name)
                if teachers[name] != "":
                    if not User.objects.filter(email=teachers[name]).exists():
                        error = True
                        context['error'] = "The email %s is either incorrect or doesn't belong to a user. Your " \
                                           "information has not been saved." % teachers[name]
                        break
                    if list(teachers.values()).count(teachers[name]) > 1:
                        error = True
                        context['error'] = "You have repeated the email ' %s ' twice. Please remove one instance and " \
                                           "try again." % teachers[name]
            if not error:
                profile.set_teachers(teachers)
                profile.save()
                context['saved'] = True
        else:
            context['error'] = "Invalid Email(s)"

    initial = {}

    teacher = profile.get_teachers()

    for name in names:
        initial[name] = teacher.get(name)

    form = TeacherForm(initial)

    context['form'] = form

    return render(request, "settings_teacher.html", context)


@login_required(login_url="login")
def assignment(request):
    if request.user.teacher:
        context = {"form": AssignmentForm()}
        if request.method == "POST":
            user = request.user
            form = AssignmentForm(request.POST)

            if form.is_valid():
                a = Assignment(
                    assignment_description=form.cleaned_data.get("assignment_description"),
                    assignment_name=form.cleaned_data.get("assignment_name"),
                )
                a.save()
                user.assignments.add(a)
                user.save()
                return redirect("home")

        return render(request, "assignment.html", context)
    else:
        return redirect("home")
