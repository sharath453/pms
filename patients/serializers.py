from rest_framework import serializers

class PatientSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(choices=['male', 'female', 'other', 'unknown'])
    birth_date = serializers.DateField()
