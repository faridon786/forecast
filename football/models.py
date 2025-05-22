from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.


class Profile(models.Model):
    """User profile model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile', verbose_name='کاربر')
    points = models.IntegerField(default=0, verbose_name='امتیاز')
    has_paid = models.BooleanField(default=False, verbose_name='پرداخت شده')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='آواتار')
    bio = models.TextField(max_length=500, blank=True, verbose_name='درباره من')
    location = models.CharField(max_length=100, blank=True, verbose_name='موقعیت')
    birth_date = models.DateField(null=True, blank=True, verbose_name='تاریخ تولد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')

    class Meta:
        verbose_name = 'پروفایل'
        verbose_name_plural = 'پروفایل‌ها'

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_leaderboard_position(self):
        return Profile.objects.filter(points__gt=self.points).count() + 1

# Signal to create Profile when User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Signal to create a Profile when a new User is created"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Signal to save the Profile when User is saved"""
    if hasattr(instance, 'user_profile'):
        instance.user_profile.save()



class Sport(models.Model):
    SPORT_CHOICES = [
        ('football', 'فوتبال'),
        ('volleyball', 'والیبال'),
        ('basketball', 'بسکتبال'),
    ]
    
    name = models.CharField(max_length=20, choices=SPORT_CHOICES, unique=True)
    display_name = models.CharField(max_length=50)
    icon = models.CharField(max_length=50, default='fas fa-futbol')  # Font Awesome icon class
    
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
    is_finished = models.BooleanField(default=False, verbose_name='پایان یافته')
    real_home_team_score = models.IntegerField(null=True, blank=True, verbose_name='امتیاز واقعی تیم میزبان')
    real_away_team_score = models.IntegerField(null=True, blank=True, verbose_name='امتیاز واقعی تیم مهمان')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')

    class Meta:
        verbose_name = 'مسابقه'
        verbose_name_plural = 'مسابقات'
        ordering = ['date']

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
            
        if (self.home_team_score == self.match.real_home_team_score and 
            self.away_team_score == self.match.real_away_team_score):
            self.is_correct = True
            self.save()
            
            # Update user's points
            profile = Profile.objects.get(user=self.user)
            profile.points += 3  # Award 3 points for correct prediction
            profile.save()
            
            return True
        return False



class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    transaction_id = models.CharField(max_length=255, unique=True, verbose_name='شناسه تراکنش')
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='مبلغ (دلار)')
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
        self.status = 'verified'
        self.verified_at = timezone.now()
        self.save()
        
        # Update user's payment status
        profile = Profile.objects.get(user=self.user)
        profile.has_paid = True
        profile.save()

    def reject(self, reason=""):
        self.status = 'rejected'
        self.notes = reason
        self.save()

    def expire(self):
        self.status = 'expired'
        self.save()



@receiver(post_save, sender=Match)
def check_predictions_on_match_finish(sender, instance, **kwargs):
    """Signal to check all predictions when a match is finished"""
    if instance.is_finished:
        predictions = Prediction.objects.filter(match=instance)
        for prediction in predictions:
            prediction.check_prediction()


