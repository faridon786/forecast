from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def sub(value, arg):
    """Subtract the arg from the value."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def referral_link(profile):
    """Get the referral link for a profile"""
    return profile.get_referral_link() 