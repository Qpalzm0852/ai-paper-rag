from django.urls import path

from . import views

urlpatterns = [
    path('api/ask/', views.ask_paper, name='ask_paper'),
    path('api/ask-json/', views.ask_paper_json, name='ask_paper_json'),
    path('api/upload/', views.upload_paper, name='upload_paper'),
    path('api/documents/', views.documents_api, name='documents_api'),
    path('api/status/', views.status_api, name='status_api'),
    path('api/settings/', views.settings_api, name='settings_api'),
    path('api/tasks/<str:task_id>/', views.task_status_api, name='task_status_api'),
]
