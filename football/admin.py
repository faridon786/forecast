from django.contrib import admin
from .models import Team, Match, Prediction, Profile, Payment, Sport, TermsOfService, WithdrawalRequest, ContactMessage, UserSportPrediction, UserSportPayment
from django.contrib import messages
from django.db import transaction

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'sport', 'symbol')
    list_filter = ('sport',)
    search_fields = ('name', 'symbol')

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('home_team', 'away_team', 'date', 'sport', 'is_finished')
    list_filter = ('is_finished', 'sport')
    search_fields = ('home_team__name', 'away_team__name', 'date')
    date_hierarchy = 'date'
    autocomplete_fields = ['home_team', 'away_team']
    fieldsets = (
        ('اطلاعات مسابقه', {
            'fields': ('home_team', 'away_team', 'date', 'sport', 'venue', 'description')
        }),
        ('نتیجه', {
            'fields': ('home_team_score', 'away_team_score', 'is_finished')
        }),
    )

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
    readonly_fields = ('created_at', 'verified_at')
    fieldsets = (
        ('اطلاعات کاربر', {
            'fields': ('user', 'amount_usd', 'transaction_id')
        }),
        ('وضعیت', {
            'fields': ('status', 'notes')
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'verified_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            try:
                with transaction.atomic():
                    # Get the original object from the database
                    original_obj = Payment.objects.select_for_update().get(pk=obj.pk)
                    
                    # Check if status has already changed
                    if original_obj.status != 'pending':
                        self.message_user(request, "این پرداخت قبلاً پردازش شده است", level=messages.ERROR)
                        return
                    
                    if obj.status == 'verified':
                        original_obj.verify()
                        self.message_user(request, "پرداخت با موفقیت تایید شد و مبلغ به موجودی کاربر اضافه شد.", level=messages.SUCCESS)
                    elif obj.status == 'rejected':
                        original_obj.reject(form.cleaned_data.get('notes', ''))
                        self.message_user(request, "پرداخت با موفقیت رد شد.", level=messages.SUCCESS)
                    elif obj.status == 'expired':
                        original_obj.expire()
                        self.message_user(request, "پرداخت منقضی شد.", level=messages.SUCCESS)
                return
            except ValueError as e:
                self.message_user(request, str(e), level=messages.ERROR)
                return
            except Exception as e:
                self.message_user(request, "خطا در پردازش پرداخت. لطفاً دوباره تلاش کنید.", level=messages.ERROR)
                return
        
        # For non-status changes, use the default save behavior
        super().save_model(request, obj, form, change)

@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'icon')
    search_fields = ('name', 'display_name')

@admin.register(TermsOfService)
class TermsOfServiceAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('محتوا', {
            'fields': ('content',)
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'wallet_address', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'wallet_address')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('اطلاعات کاربر', {
            'fields': ('user', 'amount', 'wallet_address')
        }),
        ('وضعیت', {
            'fields': ('status', 'admin_notes')
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            try:
                with transaction.atomic():
                    # Get the original object from the database
                    original_obj = WithdrawalRequest.objects.select_for_update().get(pk=obj.pk)
                    
                    # Check if status has already changed
                    if original_obj.status != 'pending':
                        self.message_user(request, "این درخواست قبلاً پردازش شده است", level=messages.ERROR)
                        return
                    
                    if obj.status == 'approved':
                        original_obj.approve(form.cleaned_data.get('admin_notes', ''))
                        self.message_user(request, "درخواست برداشت با موفقیت تایید شد.", level=messages.SUCCESS)
                    elif obj.status == 'rejected':
                        original_obj.reject(form.cleaned_data.get('admin_notes', ''))
                        self.message_user(request, "درخواست برداشت با موفقیت رد شد.", level=messages.SUCCESS)
                return
            except ValueError as e:
                self.message_user(request, str(e), level=messages.ERROR)
                return
            except Exception as e:
                self.message_user(request, "خطا در پردازش درخواست برداشت. لطفاً دوباره تلاش کنید.", level=messages.ERROR)
                return
        
        # For non-status changes, use the default save behavior
        super().save_model(request, obj, form, change)

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')
    ordering = ('-created_at',)

@admin.register(UserSportPrediction)
class UserSportPredictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'sport', 'last_prediction', 'is_selected_for_today')
    list_filter = ('sport', 'is_selected_for_today')
    search_fields = ('user__username', 'sport__name')
    ordering = ('-last_prediction',)
    date_hierarchy = 'last_prediction'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'sport')

@admin.register(UserSportPayment)
class UserSportPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'sport', 'payment_date', 'payment_window_start', 'created_at')
    list_filter = ('sport', 'payment_date', 'payment_window_start')
    search_fields = ('user__username', 'sport__name')
    readonly_fields = ('payment_window_start', 'created_at')