from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import Prediction, Team, Match, Profile, Payment, Sport, WithdrawalRequest, ContactMessage
from django.core.validators import MinValueValidator, MaxValueValidator

class UserRegistrationForm(UserCreationForm):
    """Form for user registration"""
    email = forms.EmailField(required=True)
    terms = forms.BooleanField(required=True, error_messages={
        'required': 'لطفاً با قوانین و مقررات سایت موافقت کنید.'
    })
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('این ایمیل قبلاً ثبت شده است.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class UsernameChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام کاربری جدید را وارد کنید'
            }),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise forms.ValidationError('این نام کاربری قبلاً استفاده شده است')
        if len(username) < 3:
            raise forms.ValidationError('نام کاربری باید حداقل 3 کاراکتر باشد')
        return username

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'رمز عبور فعلی را وارد کنید'
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'رمز عبور جدید را وارد کنید'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'رمز عبور جدید را تکرار کنید'
        })

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'logo', 'symbol', 'sport']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'sport': forms.Select(attrs={'class': 'form-control'}),
        }

class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['home_team', 'away_team', 'date']
        widgets = {
            'home_team': forms.Select(attrs={'class': 'form-control'}),
            'away_team': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter teams based on the same sport
        if 'home_team' in self.data:
            try:
                home_team_id = int(self.data.get('home_team'))
                home_team = Team.objects.get(id=home_team_id)
                self.fields['away_team'].queryset = Team.objects.filter(sport=home_team.sport)
            except (ValueError, Team.DoesNotExist):
                pass
        elif self.instance.pk and self.instance.home_team:
            self.fields['away_team'].queryset = Team.objects.filter(sport=self.instance.home_team.sport)

class PredictionForm(forms.ModelForm):
    """Form for making match predictions"""
    home_team_score = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control score-input',
            'data-slider-target': 'home-slider'
        })
    )
    away_team_score = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control score-input',
            'data-slider-target': 'away-slider'
        })
    )

    class Meta:
        model = Prediction
        fields = ('home_team_score', 'away_team_score')

    def __init__(self, *args, **kwargs):
        self.match = kwargs.pop('match', None)
        super().__init__(*args, **kwargs)
        
        # Set placeholder text and validation based on sport type
        if self.match and self.match.sport:
            if self.match.sport.name == 'والیبال':
                self.fields['home_team_score'].widget.attrs['placeholder'] = f'تعداد ست {self.match.home_team.name}'
                self.fields['away_team_score'].widget.attrs['placeholder'] = f'تعداد ست {self.match.away_team.name}'
                self.fields['home_team_score'].validators = [MinValueValidator(0), MaxValueValidator(3)]
                self.fields['away_team_score'].validators = [MinValueValidator(0), MaxValueValidator(3)]
                self.fields['home_team_score'].widget.attrs['max'] = '3'
                self.fields['away_team_score'].widget.attrs['max'] = '3'
            elif self.match.sport.name == 'بسکتبال':
                self.fields['home_team_score'].widget.attrs['placeholder'] = f'امتیاز {self.match.home_team.name}'
                self.fields['away_team_score'].widget.attrs['placeholder'] = f'امتیاز {self.match.away_team.name}'
                self.fields['home_team_score'].validators = [MinValueValidator(0), MaxValueValidator(200)]
                self.fields['away_team_score'].validators = [MinValueValidator(0), MaxValueValidator(200)]
                self.fields['home_team_score'].widget.attrs['max'] = '200'
                self.fields['away_team_score'].widget.attrs['max'] = '200'
            else:  # فوتبال or other sports
                self.fields['home_team_score'].widget.attrs['placeholder'] = f'تعداد گل {self.match.home_team.name}'
                self.fields['away_team_score'].widget.attrs['placeholder'] = f'تعداد گل {self.match.away_team.name}'
                self.fields['home_team_score'].validators = [MinValueValidator(0), MaxValueValidator(20)]
                self.fields['away_team_score'].validators = [MinValueValidator(0), MaxValueValidator(20)]
                self.fields['home_team_score'].widget.attrs['max'] = '20'
                self.fields['away_team_score'].widget.attrs['max'] = '20'
        
        # Add slider fields
        self.fields['home_slider'] = forms.IntegerField(
            required=False,
            widget=forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range score-slider',
                'min': '0',
                'id': 'home-slider',
                'data-input-target': 'id_home_team_score'
            })
        )
        self.fields['away_slider'] = forms.IntegerField(
            required=False,
            widget=forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range score-slider',
                'min': '0',
                'id': 'away-slider',
                'data-input-target': 'id_away_team_score'
            })
        )

    def clean(self):
        cleaned_data = super().clean()
        home_score = cleaned_data.get('home_team_score')
        away_score = cleaned_data.get('away_team_score')
        
        if home_score is not None and away_score is not None:
            if home_score < 0 or away_score < 0:
                raise forms.ValidationError('تعداد گل نمی‌تواند منفی باشد.')
        
        return cleaned_data 

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['location', 'birth_date', 'bio']
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount_usd', 'transaction_id', 'network']
        widgets = {
            'amount_usd': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '1000'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'network': forms.Select(attrs={'class': 'form-control'})
        }

    def clean_amount_usd(self):
        amount = self.cleaned_data.get('amount_usd')
        if amount <= 0:
            raise forms.ValidationError("مبلغ باید بیشتر از صفر باشد")
        if amount > 1000:
            raise forms.ValidationError("مبلغ نمی‌تواند بیشتر از 1000 دلار باشد")
        return amount

    def clean_transaction_id(self):
        transaction_id = self.cleaned_data.get('transaction_id')
        if Payment.objects.filter(transaction_id=transaction_id).exists():
            raise forms.ValidationError("این شناسه تراکنش قبلاً استفاده شده است")
        return transaction_id

class WithdrawalRequestForm(forms.ModelForm):
    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'wallet_address']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'step': '0.01'}),
            'wallet_address': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'amount': 'مبلغ (دلار)',
            'wallet_address': 'آدرس کیف پول',
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            # Get the user's profile
            user = self.instance.user if self.instance.pk else None
            if user:
                profile = user.user_profile
                # Calculate available balance (total - locked $5)
                available_balance = max(0, profile.balance - 5)
                
                if amount > available_balance:
                    raise forms.ValidationError(f'مبلغ قابل برداشت شما {available_balance} دلار است. (5 دلار اولیه قفل شده است)')
                
                if amount < 5:
                    raise forms.ValidationError('حداقل مبلغ برداشت 5 دلار است.')
                
                # Ensure user has enough balance including the locked $5
                if amount + 5 > profile.balance:
                    raise forms.ValidationError('موجودی کافی نیست. لطفاً توجه داشته باشید که 5 دلار اولیه قابل برداشت نیست.')
        
        return amount

class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام شما'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ایمیل شما'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'موضوع'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'متن پیام', 'rows': 5}),
        } 