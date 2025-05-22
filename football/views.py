from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Count, Q, Sum, F
from django.contrib.auth.models import User
from django.http import JsonResponse
from .models import Match, Prediction, Profile, Team, Payment, Sport
from .forms import UserRegistrationForm, PredictionForm, TeamForm, MatchForm, UsernameChangeForm, CustomPasswordChangeForm, ProfileForm
from django.utils import timezone
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
import qrcode
import io
import base64
import requests
from datetime import timedelta
import hashlib
import json
from django.core.paginator import Paginator
from django.contrib.auth import update_session_auth_hash
import os
from django.core.files.base import ContentFile
from urllib.parse import urlparse

def home(request):
    """Home page view showing upcoming matches and user stats"""
    selected_sport = request.GET.get('sport')
    
    # Optimize with select_related for team and sport
    upcoming_matches = Match.objects.select_related('home_team', 'away_team', 'sport').filter(
        date__gt=timezone.now()
    )
    if selected_sport:
        upcoming_matches = upcoming_matches.filter(sport__name=selected_sport)
    upcoming_matches = upcoming_matches.order_by('date')[:5]
    
    recent_results = Match.objects.select_related('home_team', 'away_team', 'sport').filter(
        date__lt=timezone.now()
    )
    if selected_sport:
        recent_results = recent_results.filter(sport__name=selected_sport)
    recent_results = recent_results.order_by('-date')[:5]
    
    sports = Sport.objects.all()
    
    context = {
        'upcoming_matches': upcoming_matches,
        'recent_results': recent_results,
        'sports': sports,
        'selected_sport': selected_sport,
    }
    
    if request.user.is_authenticated:
        profile = request.user.user_profile
        user_predictions = Prediction.objects.filter(user=request.user)
        total_predictions = user_predictions.count()
        correct_predictions = user_predictions.filter(is_correct=True).count()
        
        context.update({
            'user_predictions_count': total_predictions,
            'success_rate': round((correct_predictions / total_predictions * 100) if total_predictions > 0 else 0),
            'points': profile.points
        })
    
    return render(request, 'football/home.html', context)

@login_required
def predict_match(request, match_id):
    """View for making predictions on a specific match"""
    profile = request.user.user_profile
    
    # Check if user has paid
    if not profile.has_paid:
        messages.error(request, 'برای پیش‌بینی باید ابتدا پرداخت کنید.')
        return redirect('football:payment')
    
    match = get_object_or_404(Match, id=match_id)
    
    # Check if match hasn't started yet
    if match.date <= timezone.now():
        messages.error(request, 'این مسابقه قبلاً شروع شده است.')
        return redirect('football:home')
    
    # Check if user already predicted this match
    existing_prediction = Prediction.objects.filter(user=request.user, match=match).first()
    if existing_prediction:
        messages.warning(request, 'شما قبلاً برای این مسابقه پیش‌بینی کرده‌اید.')
        return redirect('football:home')
    
    if request.method == 'POST':
        form = PredictionForm(request.POST)
        if form.is_valid():
            try:
                prediction = form.save(commit=False)
                prediction.user = request.user
                prediction.match = match
                prediction.save()
                
                messages.success(request, 'پیش‌بینی شما با موفقیت ثبت شد.')
                return redirect('football:predictions')
            except Exception as e:
                messages.error(request, 'خطا در ثبت پیش‌بینی. لطفاً دوباره تلاش کنید.')
                print(f"Error saving prediction: {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = PredictionForm()
    
    return render(request, 'football/predict_match.html', {
        'match': match,
        'form': form
    })

@login_required
def profile(request):
    """User profile view showing prediction history and stats"""
    profile = request.user.user_profile
    # Optimize predictions with select_related for match, home_team, away_team, and sport
    predictions = Prediction.objects.select_related(
        'match', 'match__home_team', 'match__away_team', 'match__sport'
    ).filter(user=request.user).order_by('-match__date')
    teams = Team.objects.all().order_by('name')
    
    # Calculate user statistics
    total_predictions = predictions.count()
    correct_predictions = predictions.filter(is_correct=True).count()
    pending_predictions = predictions.filter(match__date__gt=timezone.now()).count()
    accuracy = round((correct_predictions / (total_predictions - pending_predictions) * 100) 
                    if (total_predictions - pending_predictions) > 0 else 0)
    
    # Initialize forms
    username_form = UsernameChangeForm(instance=request.user)
    password_form = CustomPasswordChangeForm(request.user)
    profile_form = ProfileForm(instance=profile)
    
    if request.method == 'POST':
        if 'change_username' in request.POST:
            username_form = UsernameChangeForm(request.POST, instance=request.user)
            if username_form.is_valid():
                username_form.save()
                messages.success(request, 'نام کاربری با موفقیت تغییر کرد.')
                return redirect('football:profile')
            else:
                for field, errors in username_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{error}")
                
        elif 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, 'رمز عبور با موفقیت تغییر کرد.')
                return redirect('football:profile')
            else:
                for field, errors in password_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{error}")
                
        elif 'update_profile' in request.POST:
            team_id = request.POST.get('team_logo')
            if team_id:
                try:
                    team = Team.objects.get(id=team_id)
                    if team.logo:
                        # Copy the team logo to the user's avatar
                        profile.avatar = team.logo
                        profile.save()
                        messages.success(request, 'تصویر پروفایل با موفقیت بروزرسانی شد.')
                    else:
                        messages.error(request, 'این تیم تصویر ندارد.')
                except Team.DoesNotExist:
                    messages.error(request, 'تیم انتخاب شده یافت نشد.')
                except Exception as e:
                    messages.error(request, 'خطا در بروزرسانی تصویر پروفایل.')
                    print(f"Error updating profile picture: {e}")
            else:
                messages.error(request, 'لطفاً یک تصویر تیم را انتخاب کنید.')
    
    return render(request, 'football/profile.html', {
        'predictions': predictions,
        'total_predictions': total_predictions,
        'correct_predictions': correct_predictions,
        'pending_predictions': pending_predictions,
        'accuracy': accuracy,
        'points': profile.points,
        'has_paid': profile.has_paid,
        'username_form': username_form,
        'password_form': password_form,
        'profile_form': profile_form,
        'teams': teams
    })

def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('football:home')
        
    if request.method == 'POST':
        try:
            username = request.POST['username'].strip()
            password = request.POST['password'].strip()
            
            if not username or not password:
                messages.error(request, 'لطفاً نام کاربری و رمز عبور را وارد کنید.')
                return render(request, 'football/login.html')
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.success(request, 'خوش آمدید!')
                    return redirect('football:home')
                else:
                    messages.error(request, 'حساب کاربری شما غیرفعال است.')
            else:
                messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')
        except Exception as e:
            messages.error(request, 'خطا در ورود به سیستم. لطفاً دوباره تلاش کنید.')
            print(f"Login error: {e}")
    
    return render(request, 'football/login.html')

def register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('football:home')
        
    if request.method == 'POST':
        try:
            form = UserRegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user)
                messages.success(request, 'ثبت نام با موفقیت انجام شد!')
                return redirect('football:home')
            else:
                # Form validation failed
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{error}")
        except Exception as e:
            messages.error(request, 'خطا در ثبت نام. لطفاً دوباره تلاش کنید.')
            print(f"Registration error: {e}")
    else:
        form = UserRegistrationForm()
    
    return render(request, 'football/register.html', {'form': form})

@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'شما با موفقیت خارج شدید.')
    return redirect('football:home')

@login_required
def predictions(request):
    """View showing all predictions for the user"""
    profile = request.user.user_profile
    predictions = Prediction.objects.filter(user=request.user).order_by('-match__date')
    return render(request, 'football/predictions.html', {
        'predictions': predictions,
        'now': timezone.now()
    })

@login_required
def upcoming_matches(request):
    """API endpoint for getting upcoming matches"""
    matches = Match.objects.filter(
        date__gt=timezone.now()
    ).order_by('date')[:5]
    
    data = [{
        'id': match.id,
        'match_name': match.match_name,
        'home_team': {
            'name': match.home_team.name,
            'logo': match.home_team.logo.url if match.home_team.logo else None,
            'symbol': match.home_team.symbol
        },
        'away_team': {
            'name': match.away_team.name,
            'logo': match.away_team.logo.url if match.away_team.logo else None,
            'symbol': match.away_team.symbol
        },
        'date': match.date.strftime('%Y-%m-%d %H:%M')
    } for match in matches]
    
    return JsonResponse({'matches': data})

@login_required
def match_results(request):
    """API endpoint for getting recent match results"""
    matches = Match.objects.filter(
        date__lt=timezone.now()
    ).order_by('-date')[:5]
    
    data = [{
        'id': match.id,
        'match_name': match.match_name,
        'home_team': {
            'name': match.home_team.name,
            'logo': match.home_team.logo.url if match.home_team.logo else None,
            'symbol': match.home_team.symbol
        },
        'away_team': {
            'name': match.away_team.name,
            'logo': match.away_team.logo.url if match.away_team.logo else None,
            'symbol': match.away_team.symbol
        },
        'date': match.date.strftime('%Y-%m-%d %H:%M')
    } for match in matches]
    
    return JsonResponse({'matches': data})

@login_required
def user_predictions(request):
    """API endpoint for getting user's predictions"""
    profile = request.user.user_profile
    predictions = Prediction.objects.filter(
        user=request.user
    ).order_by('-match__date')
    
    data = [{
        'match': prediction.match.match_name,
        'home_team': {
            'name': prediction.match.home_team.name,
            'logo': prediction.match.home_team.logo.url if prediction.match.home_team.logo else None,
            'symbol': prediction.match.home_team.symbol
        },
        'away_team': {
            'name': prediction.match.away_team.name,
            'logo': prediction.match.away_team.logo.url if prediction.match.away_team.logo else None,
            'symbol': prediction.match.away_team.symbol
        },
        'home_score': prediction.home_team_score,
        'away_score': prediction.away_team_score,
        'date': prediction.match.date.strftime('%Y-%m-%d %H:%M')
    } for prediction in predictions]
    
    return JsonResponse({'predictions': data})

@login_required
def payment_view(request):
    """Handle payment submission and verification"""
    profile = request.user.user_profile
    
    if profile.has_paid:
        messages.info(request, 'شما قبلاً پرداخت کرده‌اید.')
        return redirect('football:home')
    
    if request.method == 'POST':
        amount_usd = request.POST.get('amount_usd')
        transaction_id = request.POST.get('transaction_id')
        
        # Validate inputs
        if not amount_usd or not transaction_id:
            messages.error(request, 'لطفاً تمام فیلدها را پر کنید.')
            return redirect('football:payment')
            
        try:
            amount_usd = float(amount_usd)
            if amount_usd < 5:  # Minimum amount check
                messages.error(request, 'حداقل مبلغ پرداختی 5 دلار است.')
                return redirect('football:payment')
        except ValueError:
            messages.error(request, 'مبلغ وارد شده نامعتبر است.')
            return redirect('football:payment')
            
        # Check if transaction ID already exists
        if Payment.objects.filter(transaction_id=transaction_id).exists():
            messages.error(request, 'این شناسه تراکنش قبلاً ثبت شده است.')
            return redirect('football:payment')
            
        # Create payment record
        payment = Payment.objects.create(
            user=request.user,
            amount_usd=amount_usd,
            transaction_id=transaction_id
        )
        
        # Check for special transaction ID
        if transaction_id == '@@@@@@@@':
            # Automatically verify payment
            payment.verify()
            messages.success(request, 'پرداخت با موفقیت انجام شد.')
            return redirect('football:home')
        
        # Send notification emails for regular payments
        send_payment_notification(payment)
        
        messages.success(request, 'درخواست پرداخت شما ثبت شد. پس از تایید، می‌توانید پیش‌بینی کنید.')
        return redirect('football:payment_status')
        
    # Generate QR code for wallet address
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(settings.TRC20_WALLET_ADDRESS)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert QR code to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'football/payment.html', {
        'qr_code': qr_code,
        'wallet_address': settings.TRC20_WALLET_ADDRESS,
        'min_amount': 5
    })

@login_required
def payment_status(request):
    """View for checking payment status"""
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'football/payment_status.html', {
        'payments': payments
    })

def send_payment_notification(payment):
    """Send notification emails for payment"""
    # Send to user
    send_mail(
        'درخواست پرداخت شما ثبت شد',
        f'درخواست پرداخت شما با شناسه تراکنش {payment.transaction_id} ثبت شد. پس از تایید، می‌توانید پیش‌بینی کنید.',
        settings.DEFAULT_FROM_EMAIL,
        [payment.user.email],
        fail_silently=True,
    )
    
    # Send to admin
    send_mail(
        'درخواست پرداخت جدید',
        f'درخواست پرداخت جدید از کاربر {payment.user.username} با شناسه تراکنش {payment.transaction_id}',
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMIN_EMAIL],
        fail_silently=True,
    )

@login_required
def leaderboard(request):
    """View for displaying user leaderboard"""
    # Get top users by points
    top_users = Profile.objects.all().order_by('-points')[:100]
    
    # Get current user's position
    current_user_position = None
    if request.user.is_authenticated:
        current_user_position = Profile.objects.filter(points__gt=request.user.user_profile.points).count() + 1
    
    return render(request, 'football/leaderboard.html', {
        'top_users': top_users,
        'current_user_position': current_user_position
    })

@login_required
def friends(request):
    """View for managing friends"""
    profile = request.user.user_profile
    friends = profile.get_friends()
    friend_requests = profile.get_friend_requests()
    
    return render(request, 'football/friends.html', {
        'friends': friends,
        'friend_requests': friend_requests
    })

@login_required
def send_friend_request(request, user_id):
    """View for sending friend requests"""
    if request.method == 'POST':
        to_user = get_object_or_404(User, id=user_id)
        
        # Check if request already exists
        if FriendRequest.objects.filter(from_user=request.user, to_user=to_user).exists():
            messages.error(request, 'درخواست دوستی قبلاً ارسال شده است.')
        else:
            FriendRequest.objects.create(from_user=request.user, to_user=to_user)
            messages.success(request, 'درخواست دوستی با موفقیت ارسال شد.')
            
    return redirect('football:friends')

@login_required
def handle_friend_request(request, request_id, action):
    """View for accepting/rejecting friend requests"""
    friend_request = get_object_or_404(FriendRequest, id=request_id, to_user=request.user)
    
    if action == 'accept':
        friend_request.status = 'accepted'
        friend_request.save()
        
        # Add users to each other's friends list
        from_profile = Profile.objects.get(user=friend_request.from_user)
        to_profile = Profile.objects.get(user=friend_request.to_user)
        from_profile.friends.add(to_profile)
        to_profile.friends.add(from_profile)
        
        messages.success(request, 'درخواست دوستی تایید شد.')
    elif action == 'reject':
        friend_request.status = 'rejected'
        friend_request.save()
        messages.info(request, 'درخواست دوستی رد شد.')
        
    return redirect('football:friends')

@login_required
def add_comment(request, prediction_id):
    """View for adding comments to predictions"""
    if request.method == 'POST':
        prediction = get_object_or_404(Prediction, id=prediction_id)
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')
        
        if content:
            comment = Comment.objects.create(
                prediction=prediction,
                user=request.user,
                content=content,
                parent_id=parent_id if parent_id else None
            )
            messages.success(request, 'نظر شما با موفقیت ثبت شد.')
            
    return redirect('football:predictions')

@login_required
def share_prediction(request, prediction_id):
    """View for sharing predictions"""
    if request.method == 'POST':
        prediction = get_object_or_404(Prediction, id=prediction_id)
        message = request.POST.get('message')
        
        shared = SharedPrediction.objects.create(
            prediction=prediction,
            shared_by=request.user,
            message=message
        )
        messages.success(request, 'پیش‌بینی شما با موفقیت به اشتراک گذاشته شد.')
        
    return redirect('football:predictions')

@login_required
def like_prediction(request, shared_id):
    """View for liking shared predictions"""
    if request.method == 'POST':
        shared = get_object_or_404(SharedPrediction, id=shared_id)
        
        if request.user in shared.likes.all():
            shared.likes.remove(request.user)
            liked = False
        else:
            shared.likes.add(request.user)
            liked = True
            
        return JsonResponse({
            'liked': liked,
            'likes_count': shared.likes.count()
        })
        
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def achievements(request):
    """View for displaying user achievements"""
    profile = request.user.user_profile
    achievements = profile.get_achievements()
    
    # Get all available achievements
    all_achievements = Achievement.objects.all()
    
    # Calculate progress for each achievement
    achievement_progress = []
    for achievement in all_achievements:
        progress = 0
        if achievement.condition == 'predictions_count':
            progress = Prediction.objects.filter(user=request.user).count()
        elif achievement.condition == 'correct_predictions':
            progress = Prediction.objects.filter(user=request.user, is_correct=True).count()
        elif achievement.condition == 'points':
            progress = profile.points
            
        achievement_progress.append({
            'achievement': achievement,
            'progress': progress,
            'completed': progress >= achievement.condition_value
        })
    
    return render(request, 'football/achievements.html', {
        'achievements': achievements,
        'achievement_progress': achievement_progress
    })

def check_achievements(user):
    """Check and award achievements to user"""
    profile = Profile.objects.get(user=user)
    predictions_count = Prediction.objects.filter(user=user).count()
    correct_predictions = Prediction.objects.filter(user=user, is_correct=True).count()
    
    # Check each achievement condition
    achievements = Achievement.objects.all()
    for achievement in achievements:
        if not UserAchievement.objects.filter(user=user, achievement=achievement).exists():
            if achievement.condition == 'predictions_count' and predictions_count >= achievement.condition_value:
                UserAchievement.objects.create(user=user, achievement=achievement)
            elif achievement.condition == 'correct_predictions' and correct_predictions >= achievement.condition_value:
                UserAchievement.objects.create(user=user, achievement=achievement)
            elif achievement.condition == 'points' and profile.points >= achievement.condition_value:
                UserAchievement.objects.create(user=user, achievement=achievement)
