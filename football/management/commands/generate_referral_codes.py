from django.core.management.base import BaseCommand
from football.models import Profile
import random
import string

class Command(BaseCommand):
    help = 'Generates referral codes for users who don\'t have one'

    def handle(self, *args, **kwargs):
        profiles = Profile.objects.filter(referral_code__isnull=True)
        count = 0
        
        for profile in profiles:
            # Generate unique code
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not Profile.objects.filter(referral_code=code).exists():
                    break
            
            profile.referral_code = code
            profile.save()
            count += 1
            
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated referral codes for {count} users')
        ) 