"""Chennai & Tamil Nadu Emergency Hospital Catalog.

Standardized FHIR R4 Organization resources with custom extensions:
- http://golden.org/fhir/trauma-level (LEVEL_1 | LEVEL_2)
- http://golden.org/fhir/icu-beds
- http://golden.org/fhir/er-beds
- http://golden.org/fhir/latitude
- http://golden.org/fhir/longitude

Spans Central, North, South/GST, West/Poonamallee, OMR/ECR, and Chengalpattu/Kanchipuram highway corridors.
"""

from typing import List, Dict, Any

CHENNAI_EMERGENCY_HOSPITALS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1. Central Chennai
    # -------------------------------------------------------------
    {
        "resourceType": "Organization",
        "id": "hosp-rajiv-gandhi-gh",
        "name": "Rajiv Gandhi Government General Hospital (RGGGH)",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914425305000"}],
        "address": [{"line": ["EVR Periyar Salai, Park Town"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600003"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 24},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 35},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0827},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2707}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-kilpauk-kmc",
        "name": "Government Kilpauk Medical College Hospital (KMC)",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914428364951"}],
        "address": [{"line": ["Poonamallee High Road, Kilpauk"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600010"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 20},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 30},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0821},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2425}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-omandurar-gmssh",
        "name": "Tamil Nadu Government Multi Super Speciality Hospital (Omandurar)",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914425666000"}],
        "address": [{"line": ["Omandurar Govt Estate, Anna Salai"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600002"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 20},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0694},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2731}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-apollo-greams",
        "name": "Apollo Hospitals Greams Road",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914428290200"}],
        "address": [{"line": ["21 Greams Lane, Thousand Lights"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600006"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 30},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 35},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0573},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2512}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-royapettah-gh",
        "name": "Government Royapettah Hospital",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914428481234"}],
        "address": [{"line": ["Westcott Road, Royapettah"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600014"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 10},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 16},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0538},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2605}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-mgm-healthcare",
        "name": "MGM Healthcare Aminjikarai",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914445242424"}],
        "address": [{"line": ["Nelson Manickam Road, Aminjikarai"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600029"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 28},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0722},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2177}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-billroth-shenoy",
        "name": "Billroth Hospitals Shenoy Nagar",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914426641777"}],
        "address": [{"line": ["43 Lakshmi Talkies Road, Shenoy Nagar"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600030"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 12},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 15},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0784},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2263}
        ]
    },

    # -------------------------------------------------------------
    # 2. North Chennai
    # -------------------------------------------------------------
    {
        "resourceType": "Organization",
        "id": "hosp-stanley-medical",
        "name": "Government Stanley Medical College Hospital",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914425281351"}],
        "address": [{"line": ["Old Jail Road, Royapuram"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600001"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 18},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.1075},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2872}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-tondiarpet-gh",
        "name": "Government Peripheral Hospital Tondiarpet",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914425983456"}],
        "address": [{"line": ["G.A. Road, Tondiarpet"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600081"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 6},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 12},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.1256},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2889}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-ivan-stedeford",
        "name": "Sir Ivan Stedeford Hospital Ambattur",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914426531444"}],
        "address": [{"line": ["MTH Road, Ambattur"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600053"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 10},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 15},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.1118},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1456}
        ]
    },

    # -------------------------------------------------------------
    # 3. West Chennai / Porur / Poonamallee Corridor
    # -------------------------------------------------------------
    {
        "resourceType": "Organization",
        "id": "hosp-srmc-porur",
        "name": "Sri Ramachandra Medical College & Hospital (SRMC)",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914445928500"}],
        "address": [{"line": ["No. 1 Ramachandra Nagar, Porur"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600116"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 35},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 40},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0382},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1415}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-miot-international",
        "name": "MIOT International Hospital Manapakkam",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914442002288"}],
        "address": [{"line": ["4/112 Mount Poonamallee Road, Manapakkam"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600089"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 32},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 35},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0189},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1878}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-sims-vadapalani",
        "name": "SIMS Hospital Vadapalani",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914449211455"}],
        "address": [{"line": ["1 Jawaharlal Nehru Salai, Vadapalani"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600026"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 28},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0519},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2114}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-apollo-vanagaram",
        "name": "Apollo Speciality Hospitals Vanagaram",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914426537777"}],
        "address": [{"line": ["Vanagaram-Ambattur Main Road"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600095"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 22},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0575},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1448}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-poonamallee-gh",
        "name": "Government Hospital Poonamallee",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914426272230"}],
        "address": [{"line": ["Trunk Road, Poonamallee"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600056"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 8},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 14},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0489},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.0967}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-acs-velappanchavadi",
        "name": "ACS Medical College Hospital Velappanchavadi",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914426801580"}],
        "address": [{"line": ["Poonamallee High Road, Velappanchavadi"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600077"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 14},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 20},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0617},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1345}
        ]
    },

    # -------------------------------------------------------------
    # 4. South Chennai / GST Road Corridor
    # -------------------------------------------------------------
    {
        "resourceType": "Organization",
        "id": "hosp-chromepet-gh",
        "name": "Government Hospital Chromepet",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914422382420"}],
        "address": [{"line": ["GST Road, Chromepet"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600044"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 8},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 15},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9516},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1410}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-tambaram-gh",
        "name": "Government Hospital Tambaram Sanatorium",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914422418200"}],
        "address": [{"line": ["GST Road, Tambaram Sanatorium"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600047"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 10},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 18},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9360},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1350}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-balaji-chromepet",
        "name": "Sree Balaji Medical College & Hospital Chromepet",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914422415603"}],
        "address": [{"line": ["7 Works Road, Chromepet"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600044"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 20},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9642},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1396}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-rela-chromepet",
        "name": "Dr. Rela Institute & Medical Centre Chromepet",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914466667777"}],
        "address": [{"line": ["7 CLC Works Road, Chromepet"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600044"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 26},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 30},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9534},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1458}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-deepam-tambaram",
        "name": "Deepam Hospitals Tambaram",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914422262222"}],
        "address": [{"line": ["Mudichur Road, Tambaram West"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600045"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 8},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 12},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9240},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1235}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-hindu-mission-tambaram",
        "name": "Hindu Mission Hospital Tambaram West",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914422262244"}],
        "address": [{"line": [ "GST Road, Tambaram West"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600045"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 12},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 18},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9234},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1158}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-srm-kattankulathur",
        "name": "SRM Medical College Hospital & Research Centre",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914447432345"}],
        "address": [{"line": ["GST Road, Potheri, Kattankulathur"], "city": "Chengalpattu", "state": "Tamil Nadu", "postalCode": "603203"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 28},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 35},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.8231},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.0442}
        ]
    },

    # -------------------------------------------------------------
    # 5. OMR & ECR IT Corridor
    # -------------------------------------------------------------
    {
        "resourceType": "Organization",
        "id": "hosp-gleneagles-global",
        "name": "Gleneagles HealthCity Chennai",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914444777000"}],
        "address": [{"line": ["439 Cheran Nagar, Perumbakkam"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600100"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 30},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.8988},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1983}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-apollo-omr",
        "name": "Apollo Speciality Hospital OMR Perungudi",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914424961111"}],
        "address": [{"line": ["5/639 Rajiv Gandhi Salai (OMR), Perungudi"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600096"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 22},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9648},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2447}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-prashanth-velachery",
        "name": "Prashanth Super Speciality Hospital Velachery",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914442277777"}],
        "address": [{"line": ["36 & 36A Velachery Main Road"], "city": "Chennai", "state": "Tamil Nadu", "postalCode": "600042"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 12},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 16},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9785},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2206}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-chettinad-kelambakkam",
        "name": "Chettinad Super Speciality Hospital Kelambakkam",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914447411000"}],
        "address": [{"line": ["Rajiv Gandhi Salai (OMR), Kelambakkam"], "city": "Chengalpattu", "state": "Tamil Nadu", "postalCode": "603103"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 24},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 30},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.7885},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.2198}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-supreme-thiruporur",
        "name": "Supreme Speciality Hospitals Thiruporur",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914427445555"}],
        "address": [{"line": ["Old Mahabalipuram Road, Thiruporur"], "city": "Chengalpattu", "state": "Tamil Nadu", "postalCode": "603110"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 8},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 12},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.7246},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.1925}
        ]
    },

    # -------------------------------------------------------------
    # 6. Peripheral & Highway Corridors (Chengalpattu / Kanchipuram / Sriperumbudur)
    # -------------------------------------------------------------
    {
        "resourceType": "Organization",
        "id": "hosp-chengalpattu-gmch",
        "name": "Chengalpattu Government Medical College Hospital",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914427426566"}],
        "address": [{"line": ["GST Road, Chengalpattu"], "city": "Chengalpattu", "state": "Tamil Nadu", "postalCode": "603001"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 20},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 25},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.6845},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 79.9836}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-kanchipuram-hq",
        "name": "District Headquarters Government Hospital Kanchipuram",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914427222345"}],
        "address": [{"line": ["Hospital Road, Kanchipuram"], "city": "Kanchipuram", "state": "Tamil Nadu", "postalCode": "631501"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 16},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 22},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.8342},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 79.7036}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-sriperumbudur-gh",
        "name": "Government Hospital Sriperumbudur",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914427162234"}],
        "address": [{"line": ["Bangalore Highway (NH 48), Sriperumbudur"], "city": "Kanchipuram", "state": "Tamil Nadu", "postalCode": "602105"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_2"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 8},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 14},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 12.9734},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 79.9427}
        ]
    },
    {
        "resourceType": "Organization",
        "id": "hosp-saveetha-thandalam",
        "name": "Saveetha Medical College Hospital Thandalam",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
        "telecom": [{"system": "phone", "value": "+914466726672"}],
        "address": [{"line": ["Chennai-Bangalore Highway, Thandalam"], "city": "Kanchipuram", "state": "Tamil Nadu", "postalCode": "602105"}],
        "extension": [
            {"url": "http://golden.org/fhir/trauma-level", "valueString": "LEVEL_1"},
            {"url": "http://golden.org/fhir/icu-beds", "valueInteger": 26},
            {"url": "http://golden.org/fhir/er-beds", "valueInteger": 30},
            {"url": "http://golden.org/fhir/latitude", "valueDecimal": 13.0298},
            {"url": "http://golden.org/fhir/longitude", "valueDecimal": 80.0163}
        ]
    }
]
