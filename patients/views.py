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

@api_view(['GET', 'PUT', 'DELETE'])
def patient_detail(request, patient_id):
    """GET / PUT / DELETE patient by ID"""
    if request.method == 'GET':
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

    elif request.method == 'PUT':
        serializer = PatientSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            payload = {
                "resourceType": "Patient",
                "id": patient_id,
                "name": [{"given": [data["first_name"]], "family": data["last_name"]}],
                "gender": data["gender"],
                "birthDate": str(data["birth_date"])
            }
            try:
                r = requests.put(f"{FHIR_SERVER}/Patient/{patient_id}", json=payload)
                r.raise_for_status()
                log_operation("UPDATE", patient_id, "success", "Patient updated")
                return Response({"id": patient_id, "status": "updated", "message": "Patient updated successfully"})
            except Exception as e:
                log_operation("UPDATE", patient_id, "failed", str(e))
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        try:
            r = requests.delete(f"{FHIR_SERVER}/Patient/{patient_id}")
            if r.status_code in [200, 204]:
                log_operation("DELETE", patient_id, "success", "Patient deleted")
                return Response({"message": "Patient deleted"}, status=status.HTTP_204_NO_CONTENT)
            log_operation("DELETE", patient_id, "failed", r.text)
            return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log_operation("DELETE", patient_id, "failed", str(e))
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
    """
    Search patients by name, ID, or date (birth date).
    URL params:
        ?name=John
        ?id=123
        ?birth_date=2000-01-01
    """
    name = request.GET.get("name", "").strip()
    patient_id = request.GET.get("id", "").strip()
    birth_date = request.GET.get("birth_date", "").strip()

    if not any([name, patient_id, birth_date]):
        return Response({"error": "Provide at least one search parameter"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Build FHIR query
        query = []
        if name:
            query.append(f"name={quote(name)}")
        if patient_id:
            query.append(f"_id={quote(patient_id)}")
        if birth_date:
            query.append(f"birthdate={quote(birth_date)}")

        query_str = "&".join(query)
        r = requests.get(f"{FHIR_SERVER}/Patient?{query_str}")
        r.raise_for_status()

        results = []
        for entry in r.json().get("entry", []):
            p = entry.get("resource", {})
            name_data = p.get("name", [{}])[0]
            full_name = f"{' '.join(name_data.get('given', []))} {name_data.get('family', '')}".strip()
            results.append({
                "id": p.get("id"),
                "name": full_name,
                "gender": p.get("gender"),
                "birth_date": p.get("birthDate")
            })

        if not results:
            return Response({"error": "No patients found"}, status=status.HTTP_404_NOT_FOUND)

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
    """HTML view: list patients, recent first"""
    r = requests.get(f"{FHIR_SERVER}/Patient?_count=50&_sort=-_lastUpdated")
    patients = []
    if r.status_code == 200:
        for entry in r.json().get("entry", []):
            p = entry.get("resource", {})
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
    """HTML search page for name, ID, and birth date"""
    name = request.GET.get("name", "").strip()
    patient_id = request.GET.get("id", "").strip()
    birth_date = request.GET.get("birth_date", "").strip()
    results = []

    if any([name, patient_id, birth_date]):
        # Build FHIR query
        query = []
        if name:
            query.append(f"name={quote(name)}")
        if patient_id:
            query.append(f"_id={quote(patient_id)}")
        if birth_date:
            query.append(f"birthdate={quote(birth_date)}")
        query_str = "&".join(query)

        r = requests.get(f"{FHIR_SERVER}/Patient?{query_str}")
        if r.status_code == 200:
            for entry in r.json().get("entry", []):
                p = entry.get("resource", {})
                name_data = p.get("name", [{}])[0]
                full_name = f"{' '.join(name_data.get('given', []))} {name_data.get('family', '')}".strip()
                results.append({
                    "id": p.get("id"),
                    "name": full_name,
                    "gender": p.get("gender"),
                    "birth_date": p.get("birthDate")
                })

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
        # Delete from FHIR server
        requests.delete(f"{FHIR_SERVER}/Patient/{patient_id}")
        return redirect('list_patients_view')
    return render(request, 'patients/delete.html', {"patient": patient})
