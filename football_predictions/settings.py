# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = '/home/frasa0018/forecast1000/static'

# Media files (User uploaded files)
MEDIA_URL = '/media/'
MEDIA_ROOT = '/home/frasa0018/forecast1000/media'

# Additional static files locations
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
] 