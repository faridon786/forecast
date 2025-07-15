from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from ckeditor_uploader.fields import RichTextUploadingField
from django.db import transaction
import logging

# Create your models here.


class Profile(models.Model):
    """User profile model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile', verbose_name='کاربر')
    points = models.IntegerField(default=0, verbose_name='امتیاز')
    has_paid = models.BooleanField(default=False, verbose_name='پرداخت شده')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='موجودی (دلار)')
    bio = models.TextField(max_length=500, blank=True, verbose_name='درباره من')
    location = models.CharField(max_length=100, blank=True, verbose_name='موقعیت')
    birth_date = models.DateField(null=True, blank=True, verbose_name='تاریخ تولد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name='کد دعوت')
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals', verbose_name='دعوت شده توسط')
    referral_points = models.IntegerField(default=0, verbose_name='امتیاز دعوت')

    class Meta:
        verbose_name = 'پروفایل'
        verbose_name_plural = 'پروفایل‌ها'

    def __str__(self):
        return f"{self.user.username}'s profile"

    def generate_referral_code(self):
        """Generate a unique referral code for the user"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Profile.objects.filter(referral_code=code).exists():
                return code

    def get_referral_count(self):
        """Get the number of successful referrals"""
        return self.referrals.count()

    def add_referral_bonus(self):
        """Add $1 to the referrer's balance when they get a successful referral"""
        self.balance += 1
        self.save()

# Signal to create Profile when User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Signal to create a Profile when a new User is created"""
    if created:
        # Generate referral code first
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Profile.objects.filter(referral_code=code).exists():
                break
                
        # Create profile with the generated code
        Profile.objects.create(
            user=instance,
            referral_code=code
        )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Signal to save the Profile when User is saved"""
    if hasattr(instance, 'user_profile'):
        instance.user_profile.save()



class Sport(models.Model):
    SPORT_CHOICES = [
        ('فوتبال', 'فوتبال'),
        ('والیبال', 'والیبال'),
        ('بسکتبال', 'بسکتبال'),
    ]
    
    name = models.CharField(max_length=20, choices=SPORT_CHOICES, unique=True)
    display_name = models.CharField(max_length=50)
    icon = models.FileField(upload_to='sport_icons/', verbose_name='آیکون ورزش')
    
    def __str__(self):
        return self.get_name_display()
    
    class Meta:
        verbose_name = 'ورزش'
        verbose_name_plural = 'ورزش‌ها'



class Team(models.Model):
    """Team model for storing team information"""
    name = models.CharField(max_length=100, verbose_name='نام تیم')
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='teams', default=1, verbose_name='ورزش')
    logo = models.ImageField(upload_to='team_logos/', null=True, blank=True, verbose_name='لوگو')
    symbol = models.CharField(max_length=10, null=True, blank=True, verbose_name='نماد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')

    class Meta:
        verbose_name = 'تیم'
        verbose_name_plural = 'تیم‌ها'
        ordering = ['name']

    def __str__(self):
        return self.name



class Match(models.Model):
    """Match model for storing match information"""
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches', verbose_name='تیم میزبان')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches', verbose_name='تیم مهمان')
    date = models.DateTimeField(verbose_name='تاریخ مسابقه')
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='matches', verbose_name='ورزش')
    home_team_score = models.IntegerField(null=True, blank=True, verbose_name='امتیاز واقعی تیم میزبان')
    away_team_score = models.IntegerField(null=True, blank=True, verbose_name='امتیاز واقعی تیم مهمان')
    venue = models.CharField(max_length=200, verbose_name='محل برگزاری')
    description = models.TextField(verbose_name='توضیحات', blank=True)
    is_finished = models.BooleanField(default=False, verbose_name='پایان یافته')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')

    class Meta:
        verbose_name = 'مسابقه'
        verbose_name_plural = 'مسابقات'
        ordering = ['-date']

    def __str__(self):
        return f"{self.home_team.name} vs {self.away_team.name}"

    @property
    def match_name(self):
        return f"{self.home_team.name} vs {self.away_team.name}"



class Prediction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='predictions', verbose_name='کاربر')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='predictions', verbose_name='مسابقه')
    home_team_score = models.IntegerField(validators=[MinValueValidator(0)], verbose_name='پیش‌بینی امتیاز تیم میزبان')
    away_team_score = models.IntegerField(validators=[MinValueValidator(0)], verbose_name='پیش‌بینی امتیاز تیم مهمان')
    is_correct = models.BooleanField(default=False, verbose_name='صحیح')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.match} - {self.home_team_score}-{self.away_team_score}"

    class Meta:
        verbose_name = 'پیش‌بینی'
        verbose_name_plural = 'پیش‌بینی‌ها'
        ordering = ['-created_at']
        unique_together = ['user', 'match']

    def check_prediction(self):
        """Check if the prediction is correct and update points"""
        if not self.match.is_finished:
            return False

        actual_home = self.match.home_team_score
        actual_away = self.match.away_team_score
        pred_home = self.home_team_score
        pred_away = self.away_team_score

        points_to_award = 0
        profile = Profile.objects.get(user=self.user)

        # Exact prediction: 10 points
        if pred_home == actual_home and pred_away == actual_away:
            self.is_correct = True
            points_to_award = 10
        # Both are draws (not exact): 7 points, but still correct (green)
        elif pred_home == pred_away and actual_home == actual_away:
            self.is_correct = True
            if pred_home != actual_home:  # Not exact draw
                points_to_award = 7
            else:
                points_to_award = 10
        # Equal difference: 10 points
        elif (pred_home - pred_away) == (actual_home - actual_away):
            self.is_correct = True
            points_to_award = 10
        # Reversed prediction: 7 points
        elif pred_home == actual_away and pred_away == actual_home:
            self.is_correct = True
            points_to_award = 7
        # Wrong prediction: 2 points
        else:
            self.is_correct = False
            points_to_award = 2

            self.save()
        profile.points += points_to_award
        profile.save()

        return True



class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    transaction_id = models.CharField(max_length=255, unique=True, verbose_name='شناسه تراکنش')
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='مبلغ (دلار)')
    network = models.CharField(
        max_length=20,
        choices=[
            ('trc20', 'USDT (TRC20)'),
            ('bep20', 'BNB (BEP20)'),
            ('btc', 'Bitcoin (BTC)'),
            ('doge', 'Dogecoin (DOGE)'),
            ('trx', 'Tron (TRX)'),
            ('ada', 'Cardano (ADA)'),
            ('ton', 'TON (TON)')
        ],
        default='trc20',
        verbose_name='شبکه'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'در انتظار تایید'),
            ('verified', 'تایید شده'),
            ('rejected', 'رد شده'),
            ('expired', 'منقضی شده')
        ],
        default='pending',
        verbose_name='وضعیت'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تایید')
    notes = models.TextField(blank=True, null=True, verbose_name='یادداشت‌ها')

    class Meta:
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f"پرداخت {self.user.username} - {self.amount_usd} USD"

    def verify(self):
        """Verify the payment and add amount to user's balance"""
        if self.status != 'pending':
            raise ValueError("این پرداخت قبلاً پردازش شده است")
        
        try:
            with transaction.atomic():
                # Lock the payment record
                payment = Payment.objects.select_for_update().get(pk=self.pk)
                if payment.status != 'pending':
                    raise ValueError("این پرداخت قبلاً پردازش شده است")
                
                # Update payment status
                self.status = 'verified'
                self.verified_at = timezone.now()
                self.save()
                
                # Update user's balance
                profile = self.user.user_profile
                profile.balance += self.amount_usd
                profile.save()
                
                return True
        except Exception as e:
            logger.error(f"Error in payment verification: {str(e)}", exc_info=True)
            raise ValueError("خطا در تایید پرداخت")

    def reject(self, reason=""):
        """Reject the payment"""
        if self.status != 'pending':
            raise ValueError("این پرداخت قبلاً پردازش شده است")
        
        self.status = 'rejected'
        self.notes = reason
        self.save()

    def expire(self):
        """Expire the payment"""
        if self.status != 'pending':
            raise ValueError("این پرداخت قبلاً پردازش شده است")
        
        self.status = 'expired'
        self.save()



@receiver(post_save, sender=Match)
def check_predictions_on_match_finish(sender, instance, **kwargs):
    """Signal to check all predictions when a match is finished"""
    if instance.is_finished:
        predictions = Prediction.objects.filter(match=instance)
        for prediction in predictions:
            prediction.check_prediction()



class TermsOfService(models.Model):
    """Model for managing terms of service content"""
    content = RichTextUploadingField(verbose_name='محتوا')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')

    class Meta:
        verbose_name = 'قوانین و مقررات'
        verbose_name_plural = 'قوانین و مقررات'
        ordering = ['-updated_at']

    def __str__(self):
        return f"Terms of Service - Last updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')}"



class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار تایید'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    wallet_address = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'درخواست برداشت'
        verbose_name_plural = 'درخواست‌های برداشت'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.amount} USD - {self.get_status_display()}"

    def approve(self, admin_notes=""):
        """Approve the withdrawal request and deduct the amount from user's balance"""
        if self.status != 'pending':
            raise ValueError("این درخواست قبلاً پردازش شده است")
        
        try:
            with transaction.atomic():
                # Get the user's profile
                profile = self.user.user_profile
                
                # Check if user has sufficient balance
                if profile.balance < self.amount:
                    raise ValueError("موجودی کاربر کافی نیست")
                
                # Update withdrawal request status
                self.status = 'approved'
                self.admin_notes = admin_notes
                self.save(update_fields=['status', 'admin_notes', 'updated_at'])

                # Deduct amount from user's balance
                profile.balance -= self.amount
                profile.save(update_fields=['balance', 'updated_at'])
                
                return True
        except ValueError as ve:
            # Handle specific validation errors
            raise ve
        except Exception as e:
            # Log the error for debugging
            print(f"Error in withdrawal approval: {str(e)}")
            raise ValueError("خطا در پردازش درخواست برداشت")

    def reject(self, admin_notes=""):
        """Reject the withdrawal request"""
        if self.status != 'pending':
            return False
        
        try:
            self.status = 'rejected'
            self.admin_notes = admin_notes
            self.save()
            return True
        except Exception as e:
            print(f"Error in withdrawal rejection: {str(e)}")
            raise ValueError("خطا در رد درخواست برداشت")



class ContactMessage(models.Model):
    name = models.CharField(max_length=100, verbose_name='نام')
    email = models.EmailField(verbose_name='ایمیل')
    subject = models.CharField(max_length=200, verbose_name='موضوع')
    message = models.TextField(verbose_name='پیام')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ارسال')

    class Meta:
        verbose_name = 'پیام تماس'
        verbose_name_plural = 'پیام‌های تماس'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"



class UserSportPrediction(models.Model):
    """Track which sport category a user has predicted in"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sport_predictions')
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE)
    last_prediction = models.DateTimeField(auto_now_add=True)
    payment_date = models.DateField(null=True, blank=True)  # Store the date payment was made for
    is_selected_for_today = models.BooleanField(default=False)
    has_paid = models.BooleanField(default=False)  # Track if user has paid for this sport type

    class Meta:
        unique_together = ['user', 'sport']
        verbose_name = 'پیش‌بینی ورزشی کاربر'
        verbose_name_plural = 'پیش‌بینی‌های ورزشی کاربران'

    def __str__(self):
        return f"{self.user.username} - {self.sport.name}"

    def can_predict(self):
        """Check if user can make predictions for this sport today"""
        from django.utils import timezone
        from datetime import timedelta
        
        # If this sport is already selected for today, allow predictions
        if self.is_selected_for_today:
            return True
            
        # Check if any other sport is selected for today
        other_sport_selected = UserSportPrediction.objects.filter(
            user=self.user,
            is_selected_for_today=True
        ).exists()
        
        # If no sport is selected for today, allow this one
        if not other_sport_selected:
            self.is_selected_for_today = True
            self.save()
            return True
            
        return False

    def update_prediction_time(self):
        """Update the last prediction time"""
        from django.utils import timezone
        self.last_prediction = timezone.now()
        self.save()

    def update_payment_date(self, date):
        """Update the payment date"""
        self.payment_date = date
        self.has_paid = True
        self.save()

    @classmethod
    def reset_daily_selections(cls):
        """Reset all sport selections for the new day"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Reset selections that are older than 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        cls.objects.filter(
            last_prediction__lt=yesterday,
            is_selected_for_today=True
        ).update(is_selected_for_today=False)



class UserSportPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sport_payments')
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE)
    payment_date = models.DateField()  # The date the user paid for
    payment_window_start = models.DateTimeField(auto_now_add=True)  # When the 24-hour window starts
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'sport', 'payment_date']
        verbose_name = 'پرداخت ورزشی کاربر'
        verbose_name_plural = 'پرداخت‌های ورزشی کاربران'

    def __str__(self):
        return f"{self.user.username} - {self.sport.name} - {self.payment_date}"

    def is_window_valid(self):
        """Check if the 24-hour payment window is still valid"""
        from datetime import timedelta
        return self.payment_window_start + timedelta(hours=24) > timezone.now()

    @classmethod
    def get_valid_payment(cls, user, sport):
        """Get the most recent valid payment for a user and sport within 24 hours"""
        from datetime import timedelta
        cutoff_time = timezone.now() - timedelta(hours=24)
        return cls.objects.filter(
            user=user,
            sport=sport,
            payment_window_start__gte=cutoff_time
        ).order_by('-payment_window_start').first()