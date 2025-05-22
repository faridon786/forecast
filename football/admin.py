from django.contrib import admin
from .models import Team, Match, Prediction, Profile, Payment, Sport

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'sport', 'symbol')
    list_filter = ('sport',)
    search_fields = ('name', 'symbol')

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('match_name', 'date', 'sport', 'is_finished', 'real_home_team_score', 'real_away_team_score')
    list_filter = ('is_finished', 'sport', 'date')
    search_fields = ('home_team__name', 'away_team__name')
    date_hierarchy = 'date'

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'match', 'home_team_score', 'away_team_score', 'is_correct', 'created_at')
    list_filter = ('is_correct', 'created_at')
    search_fields = ('user__username', 'match__home_team__name', 'match__away_team__name')
    date_hierarchy = 'created_at'

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'points', 'has_paid', 'location', 'birth_date')
    list_filter = ('has_paid',)
    search_fields = ('user__username', 'location')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_usd', 'status', 'created_at', 'verified_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'transaction_id')
    date_hierarchy = 'created_at'

@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'icon')
    search_fields = ('name', 'display_name')