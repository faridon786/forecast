from django.core.management.base import BaseCommand
from football.models import Match, Prediction

class Command(BaseCommand):
    help = 'Updates points for all predictions based on match results'

    def handle(self, *args, **options):
        # Get all finished matches
        matches = Match.objects.filter(is_finished=True, points_updated=False)
        
        for match in matches:
            # Get all predictions for this match
            predictions = Prediction.objects.filter(match=match)
            
            for prediction in predictions:
                # Calculate points based on prediction accuracy
                if prediction.home_team_score == match.real_home_team_score and \
                   prediction.away_team_score == match.real_away_team_score:
                    prediction.points = 3
                    prediction.is_correct = True
                elif (prediction.home_team_score > prediction.away_team_score and \
                      match.real_home_team_score > match.real_away_team_score) or \
                     (prediction.home_team_score < prediction.away_team_score and \
                      match.real_home_team_score < match.real_away_team_score) or \
                     (prediction.home_team_score == prediction.away_team_score and \
                      match.real_home_team_score == match.real_away_team_score):
                    prediction.points = 1
                    prediction.is_correct = True
                else:
                    prediction.points = 0
                    prediction.is_correct = False
                
                prediction.save()
                
                # Update user profile points
                profile = prediction.placed_by
                profile.points += prediction.points
                profile.save()
            
            # Mark match as updated
            match.points_updated = True
            match.save()
            
            self.stdout.write(self.style.SUCCESS(f'Successfully updated points for match {match}')) 