import requests
import os
from django.shortcuts import render, redirect
from django.utils.dateparse import parse_datetime
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth import authenticate, login

# from django.http import HttpResponseRedirect
from .models import NewsSource, Dose, FavoriteDose, BookmarkDose, Comment
from .forms import CommentForm, EditCommentForm


# Create your views here.
class Home(LoginView):
    template_name = "home.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(
                "dose-index"
            )  # Redirect to the dose list view if the user is authenticated
        return super().get(request, *args, **kwargs)


class SignUpView(CreateView):
    form_class = UserCreationForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("dose-index")  # Redirect to the index page after sign-up

    def form_valid(self, form):
        response = super().form_valid(form)
        username = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password1")
        user = authenticate(username=username, password=password)
        if user is not None:
            login(self.request, user)
        return response


BASE_URL = "https://gnews.io/api/v4/top-headlines?"


def fetch_doses(category=None):
    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("API_KEY is not set in the environment variables.")
        return []

    url = f"{BASE_URL}apikey={api_key}&lang=en&expand=content&max=9&page=20"
    if category:
        url += f"&category={category}"
    print(f"Request URL: {url}")  # Debugging: Print the URL

    try:
        response = requests.get(url)
        print(f"Response Status Code: {response.status_code}")  # Debugging: Print the status code

        if response.status_code == 200:
            data = response.json()
            doses = data.get("articles", [])  # Get the first 5 articles

            # Iterate through the fetched articles and save them to the database
            for dose in doses:
                source_name = dose["source"]["name"]
                source, created = NewsSource.objects.get_or_create(name=source_name)

                # Parse the published_at field to match DateTimeField
                published_at = parse_datetime(dose["publishedAt"])

                # Check if the dose (dose) already exists based on the URL
                if not Dose.objects.filter(url=dose["url"]).exists():

                    print("length of content:", len(dose.get("content", "")))

                    # Save the dose to the database
                    Dose.objects.create(
                        title=dose["title"],
                        category=category,  # Use the category passed to the function
                        content=dose.get("content"),
                        description=dose["description"],
                        url=dose["url"],
                        image=dose["image"],
                        published_at=published_at,
                        source=source,
                    )
            return doses  # Optionally return the doses, though not necessary here
        else:
            print(f"Failed to fetch doses: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching doses: {e}")
        return []

def dose_search(request):
    query = request.GET.get("q")
    if query:
        results = Dose.objects.filter(
            title__icontains=query
        )  # Adjust the filter as needed
    else:
        results = Dose.objects.none()
    return render(
        request, "dose_search_results.html", {"results": results, "query": query}
    )


def dose_list(request):
    # Fetch and save doses from the API
    fetch_doses(category=request.GET.get("category"))

    # Retrieve the saved doses from the database
    # doses = Dose.objects.all()

    category = request.GET.get('category')
    print(category)
    if category and category != 'general':
        doses = Dose.objects.filter(category=category)
    else:
        doses = Dose.objects.all()
    categories = Dose.objects.values_list('category', flat=True).distinct()
    return render(request, 'doses/index.html', {
        'doses': doses,
        'categories': categories,
        'selected_category': category,
    })

    

    # Pass the doses to the template for rendering
    # return render(request, 'doses/index.html', {'doses': doses})

@login_required
def dose_detail(request, dose_id):
    try:
        dose = Dose.objects.get(id=dose_id)
    except Dose.DoesNotExist:
        return redirect("dose-detail")  # Redirect if the dose does not exist

    print("image:", dose.image)

    comments = dose.comments.all()
    form = CommentForm()

    # Check to see if dose is bookmarked
    is_bookmarked = BookmarkDose.objects.filter(user=request.user, dose=dose).exists()

    # Check if the dose is favorited by the current user
    is_favorited = FavoriteDose.objects.filter(user=request.user, dose=dose).exists()

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(
                "login"
            )  # Redirect to login if the user is not authenticated
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.dose = dose
            comment.user = request.user
            comment.save()
            # Redirect to the same page to display the new comment
            return redirect("dose-detail", dose_id=dose.id)

    return render(
        request,
        "doses/detail.html",
        {
            "dose": dose,
            "comments": comments,
            "form": form,
            "is_bookmarked": is_bookmarked,  # Pass the bookmark status to the template
            "is_favorited": is_favorited,  # Pass the favorite status to the template
        },
    )


@login_required
def favorite_doses_list(request):
    user = request.user
    favorite_doses = FavoriteDose.objects.filter(user=user).select_related("dose")
    return render(
        request, "doses/favorite_doses_list.html", {"favorite_doses": favorite_doses}
    )


@login_required
def bookmark_doses_list(request):
    user = request.user
    bookmarked_doses = BookmarkDose.objects.filter(user=user).select_related("dose")
    return render(
        request,
        "doses/bookmark_doses_list.html",
        {"bookmarked_doses": bookmarked_doses},
    )


@login_required
def bookmark_dose(request, dose_id):
    try:
        dose = Dose.objects.get(id=dose_id)
    except Dose.DoesNotExist:
        return redirect("bookmark-dose-index")  # Redirect if the dose does not exist

    user = request.user

    if not BookmarkDose.objects.filter(dose=dose, user=user).exists():
        BookmarkDose.objects.create(dose=dose, user=user)

    return redirect("bookmark-dose-index")


@login_required
def unbookmark_dose(request, dose_id):
    try:
        dose = Dose.objects.get(id=dose_id)
    except Dose.DoesNotExist:
        return redirect("bookmark-dose-index")  # Redirect if the dose does not exist

    user = request.user

    bookmark = BookmarkDose.objects.filter(dose=dose, user=user).first()
    if bookmark:
        bookmark.delete()

    return redirect("bookmark-dose-index")


@login_required
def favorite_dose(request, dose_id):
    try:
        dose = Dose.objects.get(id=dose_id)
    except Dose.DoesNotExist:
        return redirect("favorite-doses-index")  # Redirect if the dose does not exist

    user = request.user

    if not FavoriteDose.objects.filter(dose=dose, user=user).exists():
        FavoriteDose.objects.create(dose=dose, user=user)

    return redirect("favorite-doses-index")


@login_required
def unfavorite_dose(request, dose_id):
    try:
        dose = Dose.objects.get(id=dose_id)
    except Dose.DoesNotExist:
        return redirect("favorite-doses-index")  # Redirect if the dose does not exist

    user = request.user

    favorite = FavoriteDose.objects.filter(dose=dose, user=user).first()
    if favorite:
        favorite.delete()

    return redirect("favorite-doses-index")


@login_required
def add_comment(request, dose_id):
    try:
        dose = Dose.objects.get(id=dose_id)
    except Dose.DoesNotExist:
        return redirect("dose-index")  # Redirect if the dose does not exist

    user = request.user

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data["text"]
            Comment.objects.create(dose=dose, user=user, text=text)
            return redirect("dose-detail", dose_id=dose_id)
    else:
        form = CommentForm()

    return render(request, "doses/detail.html", {"dose": dose, "comment_form": form})


@login_required
def edit_comment(request, dose_id, comment_id):
    try:
        dose = Dose.objects.get(id=dose_id)
        comment = Comment.objects.get(id=comment_id, dose=dose)
    except (Dose.DoesNotExist, Comment.DoesNotExist):
        return redirect(
            "dose-detail", dose_id=dose_id
        )  # Redirect if the dose or comment does not exist

    if comment.user != request.user:
        return redirect(
            "dose-detail", dose_id=dose_id
        )  # Redirect if the user is not the author

    if request.method == "POST":
        form = EditCommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect("dose-detail", dose_id=dose_id)
    else:
        form = EditCommentForm(instance=comment)

    return render(
        request,
        "doses/edit_comment.html",
        {"dose": dose, "comment": comment, "form": form},
    )


@login_required
def delete_comment(request, dose_id, comment_id):
    try:
        dose = Dose.objects.get(id=dose_id)
        comment = Comment.objects.get(id=comment_id, dose=dose)
    except (Dose.DoesNotExist, Comment.DoesNotExist):
        return redirect(
            "dose-detail", dose_id=dose_id
        )  # Redirect if the dose or comment does not exist

    if comment.user != request.user:
        return redirect(
            "dose-detail", dose_id=dose_id
        )  # Redirect if the user is not the author

    comment.delete()

    return redirect("dose-detail", dose_id=dose_id)
