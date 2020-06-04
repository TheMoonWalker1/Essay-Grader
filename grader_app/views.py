import email.message
import json
import smtplib

from django import forms
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect
from requests_oauthlib import OAuth2Session

from .forms import EssayForm, LoginForm, InfoForm, ChangeForm, TeacherForm, AssignmentForm, CommentForm, RegisterForm, \
    SetupForm
from .models import Essay, Assignment, Comment
from .models import User
from django.contrib import auth
from django.db.models import Q
import json
from .tasks import grade_all
from celery.result import ResultBase
from time import sleep
import smtplib
import email.message
from .tasks import grade_essay


# Create your views here.

def login(request):
    admins = {"2023avasanth", "2023pbhandar", "2023kbhargav"}

    if request.user is not None and request.user.is_authenticated:
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

    elif request.method == "GET" or request.user is None:
        form = LoginForm()
        context['form'] = form
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


def create(request):
    if request.user.is_authenticated:
        return redirect("home")
    context = {"method": request.method}
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            error = False
            email = password = ""
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


def setup(request):
    context = {
        "method": request.method,
        "form": SetupForm()
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
    return render(request, "setup.html", context)


@login_required(login_url="login")
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
            essays = Essay.objects.filter(author=profile).filter(
                Q(title__icontains=q) |
                Q(body__icontains=q)
            ).order_by('-created_on').distinct()

            for essay in essays:
                queryset.append(essay)

        essays = list(set(queryset))

    if request.user.teacher and not request.user.admin:
        return redirect("teacher")

    if essays == []:
        essays = Essay.objects.all().order_by('-created_on')

    context = {
        "essays": essays,
        "query": str(query),
        "search": query != ""
    }

    return render(request, "index.html", context)


@login_required(login_url="login")
def submit(request):
    form = EssayForm(request.POST or None, **{'user': request.user})
    if request.method == 'POST':
        if form.is_valid():
            assignment = form.cleaned_data["assignment"]
            essay = Essay(
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                author=request.user,
                assignment=form.cleaned_data["assignment"],
                teacher=User.objects.get(email=form.cleaned_data["teachers"]),
                citation_type=form.cleaned_data["citation_type"]
            )
            essay.save()
            message = """Your student %s has just submitted an Essay for the assignment %s. \n\nYou also currently have %s submissions for that assignment.\n\n-------------------------------------------------\n\n%s\n\n%s""" % (
                request.user, assignment.assignment_name, Essay.objects.filter(assignment=assignment).count(),
                essay.title,
                essay.body[:400] + "...")
            send_email(message=message, subject="New Submission for assignment %s." % (assignment.assignment_name),
                       emails=[form.cleaned_data["teachers"]])
            return redirect("home")
    context = {
        'form': form,
    }
    return render(request, "submit.html", context)


def load_assignments(request):
    teacher = request.GET.get('teacher')
    if "-SELECT-" != teacher:
        assigns = User.objects.get(email=teacher).assignments.all()
    else:
        assigns = Assignment.objects.none()
    return render(request, 'submit_options.html', {'assignments': assigns})


def load_essay(request):
    essay_pk = request.GET.get('pk')
    essay = Essay.objects.get(pk=essay_pk)
    return render(request, 'load_essay.html', {'essay': essay})


@login_required(login_url="login")
def detail(request, pk):
    essay = Essay.objects.get(pk=pk)

    if request.method == "POST":

        form = CommentForm(request.POST or None)
        if form.is_valid():
            c = Comment(
                author=request.user,
                body=form.cleaned_data.get("Comment"),
                essay=essay
            )
            c.save()

    form = CommentForm(None)
    comments = Comment.objects.filter(essay=essay)
    context = {
        'essay': essay,
        'comments': comments,
        'form': form
    }

    return render(request, "detail.html", context)


# @login_required(login_url="login")
# def teacher(request):
#     user = request.user
#     assignments = []
#     query = ""
#     if not user.teacher:
#         return redirect("http://localhost:8000/home")
#     context = {}
#
#     if request.method == "GET":
#         query = request.GET.get('q', 'Search for an essay')
#
#     if query != "Search for an essay":
#         queryset = []
#         queries = query.split(" ")
#
#         for q in queries:
#             assignments = user.assignments.all().filter(
#                 Q(assignment_description__icontains=q) |
#                 Q(assignment_name__icontains=q)
#             ).order_by('assignment_name').distinct()
#
#             for assignment in assignments:
#                 queryset.append(assignment)
#
#         assignments = list(set(queryset))
#
#     if request.user.teacher and not request.user.admin:
#         return redirect("teacher")
#
#     if assignments == []:
#         assignments = user.assignments.all().order_by('assignment_name')
#
#     context['assignments'] = assignments
#
#     return render(request, "teacher.html", context)


# def get_celery_worker_status():
#         ERROR_KEY = "ERROR"
#         print("aaaaaa")
#         try:
#             from celery.app.control import Inspect
#             insp = Inspect()
#             print(insp is not None)
#             d = None
#             try:
#                 d = insp.stats()
#             except Exception as e:
#                 print(e)
#             print("qwqewqe")
#             if not d:
#                 print("sssssss")
#                 d = { ERROR_KEY: 'No running Celery workers were found.' }
#         except IOError as e:
#             from errno import errorcode
#             msg = "Error connecting to the backend: " + str(e)
#             if len(e.args) > 0 and errorcode.get(e.args[0]) == 'ECONNREFUSED':
#                 msg += ' Check that the RabbitMQ server is running.'
#             d = { ERROR_KEY: msg }
#             print("sdfs")
#             return d
#         except ImportError as e:
#             d = { ERROR_KEY: str(e)}
#             print("wqweqrwer")
#             return d
#         print("wqqwq")
#         return d

@login_required(login_url="login")
def grade(request, pk):  # max 7973 characters/request, <100 requests/day
    if not request.user.teacher:
        return redirect("home")

    essays = Essay.objects.all().filter(assignment=Assignment.objects.get(pk=pk))
    ids = []

    for essay in essays:
        if not essay.graded:
            ids.append(essay.id)

    results = grade_all(ids)

    # results = [v for v in ret.collect() if not isinstance(v, (ResultBase, tuple))]

    for result in results:
        # print("Original", result[1])
        essay = Essay.objects.get(id=result[0])
        essay.graded = True
        essay.marked_body = reformat(result[1])
        essay.save()

    essays = Essay.objects.all().filter(assignment=Assignment.objects.get(pk=pk))

    context = {
        'essays': essays
    }

    return render(request, "grade.html", context)


def reformat(body):
    punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~'''

    temp = body.split("\r\n")
    tempText = "<p>"

    for paragraph in temp:
        tempText += paragraph + "</p><p>"

    # print("Added para statements", tempText)

    temp = tempText.split("\t")
    tempText = "&emsp;"

    for tab in temp:
        tempText += tab + "&emsp;"

    # print("Added tab statements", tempText)

    return tempText + "</p>"


@login_required(login_url="login")
def teacher(request):
    context = {}
    user = request.user

    if not user.teacher:
        redirect("home")

    context['assignments'] = Assignment.objects.all()
    return render(request, "teacher.html", context)

def teacher_graded(request, pk):
    context = {}
    user = request.user

    if not user.teacher:
        redirect("home")

    if Assignment.objects.filter(pk=pk).exists():
        assignment = Assignment.objects.get(pk=pk)
        graded = Essay.objects.filter(assignment=assignment, graded=True)
    else:
        assignment = "None"
        graded = []
        context['error'] = "That Assignment Request Does Not Exist"
    context['assignment'] = assignment
    context['graded'] = graded
    print(graded)
    return render(request, "teacher_graded.html", context)

def teacher_not_graded(request, pk):
    context = {}
    user = request.user

    if not user.teacher:
        redirect("home")

    if Assignment.objects.filter(pk=pk).exists():
        assignment = Assignment.objects.get(pk=pk)
        not_graded = Essay.objects.filter(assignment=assignment, graded=False)
    else:
        assignment = "None"
        not_graded = []
        context['error'] = "That Assignment Request Does Not Exist"
    context['assignment'] = assignment
    context['not_graded'] = not_graded
    print(not_graded)
    return render(request, "teacher_not_graded.html", context)

@login_required(login_url="login")
def settings_changeInfo(request):
    profile = request.user

    context = {}
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
        context['error'] = "Cannot change info due to Ion login"
    context['form'] = form

    return render(request, "settings_info.html", context)


@login_required(login_url="login")
def settings_changePassword(request):
    profile = request.user

    context = {}

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
        context['error'] = 'Cannot change info due to Ion login'
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

    initial = {}

    teacher = profile.get_teachers()

    for name in names:
        initial[name] = teacher.get(name)

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
                message = """The student - %s - has added you in their teachers list.\n\nIf this is a mistake please contact them at "%s".""" % (
                    request.user.get_full_name(), request.user.email)
                emails = list()
                for teacher in teachers.values():
                    if teacher != "" and not teacher in initial.values():
                        emails.append(teacher)

                send_email(message, "New Student Alert", emails)

                context['saved'] = True
        else:
            context['error'] = "Invalid Email(s)"

    form = TeacherForm(initial)

    context['form'] = form

    teacher = profile.get_teachers()

    for name in names:
        initial[name] = teacher.get(name)

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

                students = list()
                for student in User.objects.all().filter(student=True):
                    for teacher in student.get_teachers().values():
                        if teacher != "":
                            t = User.objects.get(email=teacher)
                            if t.email == user.email:
                                students.append(student.email)

                message = """Your teacher %s has just posted a new assignment - %s.\n\nAssignment description: %s""" % (
                    user.get_full_name(), a.assignment_name, a.assignment_description)
                send_email(message, "New Assignment Alert", students)
                return redirect("home")

        return render(request, "assignment.html", context)
    else:
        return redirect("home")

def send_email(message, subject, emails):
    m = email.message.Message()
    session = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
    session.starttls()  # enable security
    session.login('essay.grader.app@gmail.com', 'grader_app@7876')  # login with mail_id and password
    for receiver_address in emails:
        m['From'] = "essay.grader.app@gmail.com"
        m['To'] = str(receiver_address)
        m['Subject'] = subject
        m.set_payload(message)
        session.sendmail('essay.grader.app@gmail.com', receiver_address, m.as_string())
    session.quit()
