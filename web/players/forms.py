from django import forms

from .models import Player, canonical_player_number


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ["player_number", "name"]

    def clean_player_number(self):
        # Accept either form: typing 0233 edits player 233 rather than creating
        # a second identity for the same person.
        return canonical_player_number(self.cleaned_data["player_number"])
