"""Temporary trial views must be released without waiting for cyclic GC."""
import gc
import weakref

import pytest

from shiftlink.mes import hpu_retrieval_experiment as X
from test_hpu_retrieval_experiment import experiment, published_history, service, pipe, E, G


@pytest.mark.parametrize('failure',[False,True])
def test_trial_view_has_no_retained_evidence_closure(experiment,monkeypatch,failure):
    args,_=experiment
    original=X._view
    references=[]
    def capture(pipeline):
        view=original(pipeline)
        references.append(weakref.ref(view))
        return view
    monkeypatch.setattr(X,'_view',capture)
    if failure:
        def fail(*a,**kw):raise RuntimeError('isolated run failure')
        monkeypatch.setattr(E,'judge_dist',fail)
    was_enabled=gc.isenabled()
    gc.disable()
    try:
        result=X.run_experiment(**args,mode='experiment')
        assert result['status']==('error' if failure else 'completed')
        assert all(ref() is None for ref in references), 'trial.evidence closure retains copied rows/vectors'
    finally:
        if was_enabled:gc.enable()
        gc.collect()


def test_only_one_copied_index_is_live_at_a_time(experiment,monkeypatch):
    args,_=experiment
    original=X._view
    references=[]
    def capture(pipeline):
        assert all(ref() is None for ref in references), 'previous independent view still occupies memory'
        view=original(pipeline)
        references.append(weakref.ref(view))
        return view
    monkeypatch.setattr(X,'_view',capture)
    result=X.run_experiment(**args,mode='experiment')
    assert result['status']=='completed',result
    assert len(references)==2 and all(ref() is None for ref in references)
