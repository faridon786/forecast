from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import Prediction, Team, Match, Profile, Payment, Sport

class UserRegistrationForm(forms.ModelForm):
    """Form for user registration"""
    email = forms.EmailField(required=True)
    password1 = forms.CharField(label='رمز عبور', widget=forms.PasswordInput)
    password2 = forms.CharField(label='تکرار رمز عبور', widget=forms.PasswordInput)
    
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

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('رمزهای عبور مطابقت ندارند')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            # Create associated profile
            Profile.objects.create(user=user)
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
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control score-input',
            'placeholder': 'تعداد گل تیم میزبان',
            'data-slider-target': 'home-slider'
        })
    )
    away_team_score = forms.IntegerField(
        min_value=0,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control score-input',
            'placeholder': 'تعداد گل تیم مهمان',
            'data-slider-target': 'away-slider'
        })
    )

    class Meta:
        model = Prediction
        fields = ('home_team_score', 'away_team_score')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add slider fields
        self.fields['home_slider'] = forms.IntegerField(
            required=False,
            widget=forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range score-slider',
                'min': '0',
                'max': '20',
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
                'max': '20',
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
        fields = ['avatar', 'bio', 'location', 'birth_date']
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png'
            }),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            if avatar.size > 2 * 1024 * 1024:  # 2MB
                raise forms.ValidationError('حجم تصویر نباید بیشتر از 2 مگابایت باشد')
            if not avatar.content_type in ['image/jpeg', 'image/png']:
                raise forms.ValidationError('فرمت تصویر باید JPG یا PNG باشد')
        return avatar

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount_usd', 'transaction_id']
        widgets = {
            'amount_usd': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
        } 