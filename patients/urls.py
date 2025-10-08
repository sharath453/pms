from django.urls import path
from . import views

urlpatterns = [

    # ---------- API Endpoints ----------
    path('api/patients/', views.create_patient, name='create_patient'),                         # POST
    path('api/patients/<str:patient_id>/', views.patient_detail, name='patient_detail'),         # GET / PUT / DELETE
    path('api/patients/allPatientCount/', views.all_patient_count, name='all_patient_count'),    # GET count
    path('api/patients/search/', views.search_patient, name='search_patient'),                   # GET search
    path('api/patients/list/', views.list_patients_by_last_updated, name='list_patients_by_last_updated'),  # GET list by date

    # ---------- HTML Views ----------
    path('', views.create_patient_view, name='create_patient_view'),                             # Home / Create
    path('patients/list/', views.list_patients_view, name='list_patients_view'),                 # List All Patients
    path('patients/search/', views.search_patients_view, name='search_patients_view'),           # Search Patients
    path('patients/<str:patient_id>/update/', views.update_patient_view, name='update_patient_view'),
    path('patients/<str:patient_id>/delete/', views.delete_patient_view, name='delete_patient_view'),
]
