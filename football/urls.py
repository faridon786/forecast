from django.urls import path
from . import views

app_name = 'football'

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('introduction/', views.introduction, name='introduction'),
    path('terms/', views.terms, name='terms'),
    path('predictions/', views.predictions, name='predictions'),
    
    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # User profile
    path('profile/', views.profile, name='profile'),
    
    # Match predictions
    path('predict/<int:match_id>/', views.predict_match, name='predict_match'),
    
    # Payment
    path('payment/', views.payment_view, name='payment'),
    path('payment/status/', views.payment_status, name='payment_status'),
    path('future-matches/', views.future_matches, name='future_matches'),
    
    # Leaderboard
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    
    # Referral system
    path('referral/', views.referral_view, name='referral'),
    
    # API endpoints for AJAX requests
    path('api/matches/upcoming/', views.upcoming_matches, name='upcoming_matches'),
    path('api/matches/results/', views.match_results, name='match_results'),
    path('api/predictions/', views.user_predictions, name='user_predictions'),
    
    # Withdrawal request
    path('withdrawal/', views.withdrawal_request, name='withdrawal_request'),
    
    # Contact page
    path('contact/', views.contact_view, name='contact'),
] 