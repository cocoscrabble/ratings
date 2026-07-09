from django import forms

from .models import Player, Rating


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ["player_number", "name"]


class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ["player", "rating", "date"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
