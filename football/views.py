from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Count, Q, Sum, F, Prefetch
from django.contrib.auth.models import User
from django.http import JsonResponse
from .models import Match, Prediction, Profile, Team, Payment, Sport, TermsOfService, WithdrawalRequest, UserSportPayment
from .forms import UserRegistrationForm, PredictionForm, TeamForm, MatchForm, UsernameChangeForm, CustomPasswordChangeForm, ProfileForm, PaymentForm, WithdrawalRequestForm, ContactMessageForm
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
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth import update_session_auth_hash
import os
from django.core.files.base import ContentFile
from urllib.parse import urlparse
import logging
from django.core.cache import cache
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

def home(request):
    """Home page view showing upcoming matches and user stats"""
    selected_sport = request.GET.get('sport')
    page = request.GET.get('page', 1)
    
    # Get upcoming matches
    upcoming_matches = Match.objects.filter(
        date__gt=timezone.now(),
        date__lte=timezone.now() + timezone.timedelta(days=5),
        is_finished=False
    )
    
    if selected_sport:
        upcoming_matches = upcoming_matches.filter(sport__name=selected_sport)
    
    upcoming_matches = upcoming_matches.order_by('date')
    
    # Add pagination
    paginator = Paginator(upcoming_matches, 5)  # Show 5 matches per page
    try:
        upcoming_matches = paginator.page(page)
    except PageNotAnInteger:
        upcoming_matches = paginator.page(1)
    except EmptyPage:
        upcoming_matches = paginator.page(paginator.num_pages)
    
    recent_results = Match.objects.select_related('home_team', 'away_team', 'sport').filter(
        date__lt=timezone.now()
    )
    if selected_sport:
        recent_results = recent_results.filter(sport__name=selected_sport)
    recent_results = recent_results.order_by('-date')[:5]
    
    sports = Sport.objects.all()
    
    # Get user statistics if authenticated
    if request.user.is_authenticated:
        # Get all predictions for the user
        user_predictions = Prediction.objects.filter(user=request.user)
        
        # Count correct and wrong predictions
        correct_predictions_count = user_predictions.filter(is_correct=True).count()
        wrong_predictions_count = user_predictions.filter(is_correct=False).count()
        
        # Calculate accuracy percentage
        total_predictions = correct_predictions_count + wrong_predictions_count
        accuracy_percentage = round((correct_predictions_count / total_predictions * 100) if total_predictions > 0 else 0)
        
        # Get user's total points
        try:
            total_points = request.user.user_profile.points
        except User.user_profile.RelatedObjectDoesNotExist:
            total_points = 0
        
        context = {
            'upcoming_matches': upcoming_matches,
            'recent_results': recent_results,
            'sports': sports,
            'selected_sport': selected_sport,
            'correct_predictions_count': correct_predictions_count,
            'wrong_predictions_count': wrong_predictions_count,
            'accuracy_percentage': accuracy_percentage,
            'total_points': total_points,
        }
    else:
        context = {
            'upcoming_matches': upcoming_matches,
            'recent_results': recent_results,
            'sports': sports,
            'selected_sport': selected_sport,
        }
    
    return render(request, 'football/home.html', context)

@login_required
def predict_match(request, match_id):
    """View for making predictions on a specific match"""
    match = get_object_or_404(Match, id=match_id)
    profile = request.user.user_profile
    
    # Check if match hasn't started yet
    if match.date <= timezone.now():
        messages.error(request, 'این مسابقه قبلاً شروع شده است.')
        return redirect('football:home')
    
    # Check if user already predicted this match
    existing_prediction = Prediction.objects.filter(user=request.user, match=match).first()
    if existing_prediction:
        messages.warning(request, 'شما قبلاً برای این مسابقه پیش‌بینی کرده‌اید.')
        return redirect('football:home')
    
    # Get match date
    match_date = match.date.date()

    # Check if user has paid for this sport on this match date (per-day logic)
    has_paid_for_match_date = UserSportPayment.objects.filter(
        user=request.user,
        sport=match.sport,
        payment_date=match_date
    ).exists()

    # Determine if payment is needed
    needs_payment = not has_paid_for_match_date
    
    if request.method == 'POST':
        form = PredictionForm(request.POST, match=match)
        if form.is_valid():
            try:
                # Calculate total payment needed
                total_payment_needed = 0
                payment_reason = []
                
                # Check if payment is needed
                if needs_payment:
                    total_payment_needed = 5
                    payment_reason.append("پیش‌بینی در این ورزش")
                
                # Check if user has enough balance
                if total_payment_needed > 0 and profile.balance < total_payment_needed:
                    messages.error(request, f'برای پیش‌بینی در این ورزش باید حداقل {total_payment_needed} دلار موجودی داشته باشید.')
                    return redirect('football:home')
                
                # Save the prediction
                prediction = form.save(commit=False)
                prediction.user = request.user
                prediction.match = match
                prediction.save()
                
                # Create UserSportPayment if payment was made (NEW LOGIC)
                if total_payment_needed > 0 and not has_paid_for_match_date:
                    UserSportPayment.objects.create(
                        user=request.user,
                        sport=match.sport,
                        payment_date=match_date
                    )
                    profile.balance -= total_payment_needed
                    profile.save()
                    messages.success(request, f'{total_payment_needed} دلار از حساب شما کسر شد ({", ".join(payment_reason)}) و پیش‌بینی شما با موفقیت ثبت شد.')
                else:
                    messages.success(request, 'پیش‌بینی شما با موفقیت ثبت شد.')
                
                return redirect('football:predictions')
            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, 'خطا در ثبت پیش‌بینی. لطفاً دوباره تلاش کنید.')
                print(f"Error saving prediction: {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = PredictionForm(match=match)
    
    return render(request, 'football/predict_match.html', {
        'match': match,
        'form': form,
        'current_balance': profile.balance,
        'needs_payment': needs_payment,
        'has_paid_for_match_date': has_paid_for_match_date
    })

@login_required
def profile(request):
    """User profile view showing prediction history and stats"""
    # Safely get user profile
    try:
        profile = request.user.user_profile
    except User.user_profile.RelatedObjectDoesNotExist:
        # Create profile if it doesn't exist
        from .models import Profile
        profile = Profile.objects.create(user=request.user)
    
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
    
    # Get referral code from URL parameter
    referral_code = request.GET.get('ref')
    referred_by = None
    if referral_code:
        try:
            referred_by = Profile.objects.get(referral_code=referral_code)
        except Profile.DoesNotExist:
            messages.warning(request, 'کد دعوت نامعتبر است.')
        
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                
                # If user was referred, update their profile and add bonus to referrer
                if referred_by:
                    user.user_profile.referred_by = referred_by
                    user.user_profile.save()
                    
                    # Award points and add $1 to referrer's balance
                    referred_by.referral_points += 5
                    referred_by.points += 5
                    referred_by.add_referral_bonus()  # Add $1 to referrer's balance
                    referred_by.save()
                    
                    messages.success(request, 'ثبت نام با موفقیت انجام شد! ۵ امتیاز و ۱ دلار به دعوت کننده اضافه شد.')
                else:
                    messages.success(request, 'ثبت نام با موفقیت انجام شد!')
                
                login(request, user)
                return redirect('football:home')
            except Exception as e:
                # Log the error for debugging
                print(f"Registration error: {e}")
                # Check if it's a profile-related error
                if "profile" in str(e).lower():
                    messages.error(request, 'خطا در ایجاد پروفایل کاربری. لطفاً دوباره تلاش کنید.')
                else:
                    messages.error(request, 'خطا در ثبت نام. لطفاً دوباره تلاش کنید.')
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = UserRegistrationForm()
    
    return render(request, 'football/register.html', {
        'form': form,
        'referral_code': referral_code
    })

@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'شما با موفقیت خارج شدید.')
    return redirect('football:home')

@login_required
def predictions(request):
    """View showing all predictions for the user"""
    predictions = Prediction.objects.filter(user=request.user).order_by('-match__date')
    return render(request, 'football/predictions.html', {
        'predictions': predictions
    })

def rate_limit(key_prefix, limit=5, period=60):
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
                
            cache_key = f"{key_prefix}_{request.user.id}"
            count = cache.get(cache_key, 0)
            
            if count >= limit:
                raise PermissionDenied("تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً کمی صبر کنید.")
                
            cache.set(cache_key, count + 1, period)
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator

@login_required
@rate_limit('payment', limit=5, period=60)
def payment_view(request):
    """Handle payment submission and verification"""
    # Get wallet addresses from settings
    trc20_wallet_address = settings.TRC20_WALLET_ADDRESS
    bnb_wallet_address = settings.BNB_WALLET_ADDRESS
    btc_wallet_address = settings.BTC_WALLET_ADDRESS
    doge_wallet_address = settings.DOGE_WALLET_ADDRESS
    trx_wallet_address = settings.TRX_WALLET_ADDRESS
    ada_wallet_address = settings.ADA_WALLET_ADDRESS
    ton_wallet_address = settings.TON_WALLET_ADDRESS

    # Generate QR codes for all wallets
    def generate_qr_code(address):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(address)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()

    # Generate QR codes
    trc20_qr_code = generate_qr_code(trc20_wallet_address)
    bnb_qr_code = generate_qr_code(bnb_wallet_address)
    btc_qr_code = generate_qr_code(btc_wallet_address)
    doge_qr_code = generate_qr_code(doge_wallet_address)
    trx_qr_code = generate_qr_code(trx_wallet_address)
    ada_qr_code = generate_qr_code(ada_wallet_address)
    ton_qr_code = generate_qr_code(ton_wallet_address)

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = form.save(commit=False)
                payment.user = request.user
                payment.save()
                messages.success(request, 'درخواست پرداخت شما با موفقیت ثبت شد')
                return redirect('payment_history')
            except Exception as e:
                logger.error(f"Error in payment submission: {str(e)}", exc_info=True)
                messages.error(request, 'خطا در ثبت پرداخت')
    else:
        form = PaymentForm()

    context = {
        'form': form,
        'trc20_wallet_address': trc20_wallet_address,
        'bnb_wallet_address': bnb_wallet_address,
        'btc_wallet_address': btc_wallet_address,
        'doge_wallet_address': doge_wallet_address,
        'trx_wallet_address': trx_wallet_address,
        'ada_wallet_address': ada_wallet_address,
        'ton_wallet_address': ton_wallet_address,
        'trc20_qr_code': trc20_qr_code,
        'bnb_qr_code': bnb_qr_code,
        'btc_qr_code': btc_qr_code,
        'doge_qr_code': doge_qr_code,
        'trx_qr_code': trx_qr_code,
        'ada_qr_code': ada_qr_code,
        'ton_qr_code': ton_qr_code,
    }
    return render(request, 'football/payment.html', context)

@login_required
def payment_status(request):
    """View for checking payment status"""
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'football/payment_status.html', {
        'payments': payments
    })

@login_required
def leaderboard(request):
    """Display the leaderboard of users"""
    # Get all users first, then handle profiles
    leaderboard = []
    users = User.objects.all()
    
    for user in users:
        # Safely get user profile and points
        try:
            profile = user.user_profile
            points = profile.points
        except User.user_profile.RelatedObjectDoesNotExist:
            # Create profile if it doesn't exist
            from .models import Profile
            profile = Profile.objects.create(user=user)
            points = 0
        
        # Get all predictions for the user
        user_predictions = Prediction.objects.filter(user=user).select_related('match', 'match__home_team', 'match__away_team')
        
        # Count correct and wrong predictions
        correct_predictions_count = user_predictions.filter(is_correct=True).count()
        wrong_predictions_count = user_predictions.filter(is_correct=False).count()
        
        # Calculate accuracy percentage
        total_predictions = correct_predictions_count + wrong_predictions_count
        accuracy_percentage = round((correct_predictions_count / total_predictions * 100) if total_predictions > 0 else 0)
        
        leaderboard.append({
            'user': user,
            'points': points,
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions_count,
            'wrong_predictions': wrong_predictions_count,
            'accuracy_percentage': accuracy_percentage,
            'predictions': user_predictions.order_by('-match__date')[:5]  # Get last 5 predictions
        })
    
    # Sort leaderboard by points (highest first)
    leaderboard.sort(key=lambda x: x['points'], reverse=True)

    context = {
        'leaderboard': leaderboard,
    }
    return render(request, 'football/leaderboard.html', context)

def terms(request):
    """View for displaying terms of service"""
    terms = TermsOfService.objects.first()
    return render(request, 'football/terms.html', {
        'terms': terms
    })

@login_required
def withdrawal_request(request):
    """Handle withdrawal requests"""
    if request.method == 'POST':
        form = WithdrawalRequestForm(request.POST)
        if form.is_valid():
            withdrawal = form.save(commit=False)
            withdrawal.user = request.user
            withdrawal.save()
            messages.success(request, 'درخواست برداشت شما با موفقیت ثبت شد و در حال بررسی است.')
            return redirect('football:withdrawal_request')
    else:
        form = WithdrawalRequestForm()
    
    # Get user's withdrawal history
    withdrawal_requests = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at')
    
    # Get user's payment history
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'football/withdrawal.html', {
        'form': form,
        'withdrawal_requests': withdrawal_requests,
        'payments': payments
    })

def contact_view(request):
    submitted = False
    if request.method == 'POST':
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            submitted = True
    else:
        form = ContactMessageForm()
    return render(request, 'football/contact.html', {'form': form, 'submitted': submitted})

@login_required
def referral_view(request):
    """View for managing referral system"""
    # Safely get user profile
    try:
        profile = request.user.user_profile
    except User.user_profile.RelatedObjectDoesNotExist:
        # Create profile if it doesn't exist
        profile = Profile.objects.create(user=request.user)
    
    # Get referral statistics
    referral_count = profile.get_referral_count()
    referral_code = profile.referral_code
    
    # Get the domain from the request
    domain = request.get_host()
    # Construct the full referral link
    referral_link = f"https://{domain}/register?ref={referral_code}"
    
    referral_points = profile.referral_points
    
    # Get list of referred users
    referred_users = Profile.objects.filter(referred_by=profile).select_related('user')
    
    context = {
        'referral_count': referral_count,
        'referral_link': referral_link,
        'referral_points': referral_points,
        'referred_users': referred_users,
    }
    
    return render(request, 'football/referral.html', context)

@login_required
def future_matches(request):
    """View showing matches beyond the 5-day window"""
    selected_sport = request.GET.get('sport')
    
    # Get matches beyond 5 days
    future_matches = Match.objects.filter(
        date__gt=timezone.now() + timezone.timedelta(days=5),
        is_finished=False
    )
    
    if selected_sport:
        future_matches = future_matches.filter(sport__name=selected_sport)
    
    future_matches = future_matches.order_by('date')
    
    sports = Sport.objects.all()
    
    context = {
        'future_matches': future_matches,
        'sports': sports,
        'selected_sport': selected_sport,
    }
    
    return render(request, 'football/future_matches.html', context)
