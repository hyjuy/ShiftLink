"""HPU entry point; all projection and storage logic is equipment-independent."""
from .incident_ontology import project_incident


def project_hpu(bundle):
    return project_incident(bundle, equipment_type='HPU')
