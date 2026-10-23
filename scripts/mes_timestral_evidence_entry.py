"""Evidence-entry candidate with the existing notification control retained."""
from scripts import mes_timestral_evidence as evidence

PARAMS=dict(raw_count=3,fraction=.5,max_age=8)

def predict_and_notify(data,current):
    display,_=evidence.predict(data,current,PARAMS)
    notices=evidence.previous.close.previous.notifications(data['observations'],display,45,5)
    return display,notices
