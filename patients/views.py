import requests
import logging
from django.conf import settings
from django.shortcuts import render, redirect
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import PatientSerializer
from .models import PatientLog
from urllib.parse import quote

FHIR_SERVER = settings.FHIR_SERVER
logger = logging.getLogger(__name__)

# ----------------- Helper -----------------
def log_operation(operation, patient_id=None, status='success', message=''):
    PatientLog.objects.create(
        operation=operation,
        patient_id=patient_id,
        status=status,
        message=message
    )
    logger.info(f"{operation} - {patient_id} - {status} - {message}")


# ----------------- API Endpoints -----------------
@api_view(['POST'])
def create_patient(request):
    serializer = PatientSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        payload = {
            "resourceType": "Patient",
            "name": [{"given": [data["first_name"]], "family": data["last_name"]}],
            "gender": data["gender"],
            "birthDate": str(data["birth_date"])
        }
        try:
            r = requests.post(f"{FHIR_SERVER}/Patient", json=payload)
            r.raise_for_status()
            pid = r.json().get("id")
            log_operation("CREATE", pid, "success", "Patient created")
            return Response({"id": pid, "message": "Patient created"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            log_operation("CREATE", None, "failed", str(e))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def patient_detail(request, patient_id):
    """GET patient by ID"""
    try:
        r = requests.get(f"{FHIR_SERVER}/Patient/{patient_id}")
        r.raise_for_status()
        patient = r.json()
        name_data = patient.get("name", [{}])[0]
        return Response({
            "id": patient.get("id"),
            "first_name": name_data.get("given", [""])[0],
            "last_name": name_data.get("family", ""),
            "gender": patient.get("gender"),
            "birth_date": patient.get("birthDate")
        })
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def all_patient_count(request):
    try:
        r = requests.get(f"{FHIR_SERVER}/Patient?_summary=count")
        r.raise_for_status()
        return Response({"count": r.json().get("total", 0)})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def search_patient(request):
    name = request.GET.get("name", "").strip()
    if not name:
        return Response({"error": "Name parameter required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        encoded_name = quote(name)
        r = requests.get(f"{FHIR_SERVER}/Patient?name={encoded_name}")
        r.raise_for_status()
        results = []
        for entry in r.json().get("entry", []):
            p = entry.get("resource", {})
            name_data = p.get("name", [{}])[0]
            full_name = f"{' '.join(name_data.get('given', []))} {name_data.get('family', '')}".strip()
            results.append({"id": p.get("id"), "name": full_name})
        if not results:
            return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"count": len(results), "results": results})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def list_patients_by_last_updated(request):
    last_updated = request.GET.get("lastUpdated", "")
    try:
        r = requests.get(f"{FHIR_SERVER}/Patient?_lastUpdated={last_updated}")
        r.raise_for_status()
        results = []
        for entry in r.json().get("entry", []):
            p = entry.get("resource", {})
            name_data = p.get("name", [{}])[0]
            full_name = f"{' '.join(name_data.get('given', []))} {name_data.get('family', '')}".strip()
            results.append({"id": p.get("id"), "name": full_name})
        return Response({"count": len(results), "results": results})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ----------------- HTML Views -----------------
def create_patient_view(request):
    if request.method == "POST":
        data = {
            "first_name": request.POST.get("first_name"),
            "last_name": request.POST.get("last_name"),
            "gender": request.POST.get("gender"),
            "birth_date": request.POST.get("birth_date"),
        }
        requests.post(f"{FHIR_SERVER}/Patient", json={
            "resourceType": "Patient",
            "name": [{"given": [data["first_name"]], "family": data["last_name"]}],
            "gender": data["gender"],
            "birthDate": data["birth_date"]
        })
        return redirect('list_patients_view')
    return render(request, 'patients/index.html')

def list_patients_view(request):
    """
    Fetches patients from FHIR server, sorted by most recently added (descending).
    Excludes patients without names (optional filter to skip invalid data).
    """
    r = requests.get(f"{FHIR_SERVER}/Patient?_count=50&_sort=-_lastUpdated")
    patients = []
    if r.status_code == 200:
        for entry in r.json().get("entry", []):
            p = entry.get("resource", {})
            # Skip patients without a name
            if not p.get("name"):
                continue
            name_data = p.get("name", [{}])[0]
            patients.append({
                "id": p.get("id"),
                "first_name": name_data.get("given", [""])[0],
                "last_name": name_data.get("family", ""),
                "gender": p.get("gender"),
                "birth_date": p.get("birthDate"),
            })
    return render(request, 'patients/list_patients.html', {"patients": patients})



def search_patients_view(request):
    name = request.GET.get("name", "")
    results = []
    if name:
        r = requests.get(f"{FHIR_SERVER}/Patient?name={name}")
        if r.status_code == 200:
            for entry in r.json().get("entry", []):
                p = entry.get("resource", {})
                name_data = p.get("name", [{}])[0]
                full_name = f"{' '.join(name_data.get('given', []))} {name_data.get('family', '')}".strip()
                results.append({"id": p.get("id"), "name": full_name})
    return render(request, 'patients/search.html', {"results": results})


def update_patient_view(request, patient_id):
    r = requests.get(f"{FHIR_SERVER}/Patient/{patient_id}")
    patient = {}
    if r.status_code == 200:
        p = r.json()
        name_data = p.get("name", [{}])[0]
        patient = {
            "id": p.get("id"),
            "first_name": name_data.get("given", [""])[0],
            "last_name": name_data.get("family", ""),
            "gender": p.get("gender"),
            "birth_date": p.get("birthDate"),
        }

    if request.method == "POST":
        data = {
            "first_name": request.POST.get("first_name"),
            "last_name": request.POST.get("last_name"),
            "gender": request.POST.get("gender"),
            "birth_date": request.POST.get("birth_date"),
        }
        # Send PUT request to FHIR server
        requests.put(f"{FHIR_SERVER}/Patient/{patient_id}", json={
            "resourceType": "Patient",
            "id": patient_id,
            "name": [{"given": [data["first_name"]], "family": data["last_name"]}],
            "gender": data["gender"],
            "birthDate": data["birth_date"]
        })
        return redirect('list_patients_view')
    return render(request, 'patients/update.html', {"patient": patient})


def delete_patient_view(request, patient_id):
    r = requests.get(f"{FHIR_SERVER}/Patient/{patient_id}")
    patient = {}
    if r.status_code == 200:
        p = r.json()
        name_data = p.get("name", [{}])[0]
        patient = {
            "id": p.get("id"),
            "first_name": name_data.get("given", [""])[0],
            "last_name": name_data.get("family", ""),
        }

    if request.method == "POST":
        requests.delete(f"{FHIR_SERVER}/Patient/{patient_id}")
        return redirect('list_patients_view')
    return render(request, 'patients/delete.html', {"patient": patient})
