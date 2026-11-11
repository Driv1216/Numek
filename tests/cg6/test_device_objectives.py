"""Same-weight objective/gradient/optimizer checks; no predictive-quality gate."""
from dataclasses import replace
import numpy as np
import pytest
from confidenceguard.execution.adapters import torch_architecture
from confidenceguard.auxiliary.fitting import loss
from .helpers import execution


@pytest.mark.parametrize('device',['mps','cuda'])
@pytest.mark.parametrize('kind,head,dimension',[('scale','positive',1),('quantiles','quantiles',3),('failure_risk','sigmoid',1)])
def test_same_weight_objective_backward_optimizer_step(tmp_path,device,kind,head,dimension):
    import torch
    if not (torch.backends.mps.is_available() if device=='mps' else torch.cuda.is_available()):pytest.skip('not_run_hardware_unavailable: '+device+' objective/backward/optimizer qualification')
    s=execution(tmp_path,regression=True);p=replace(s.predictors[0],architecture={'kind':'mlp','input_dim':1,'hidden':[],'output_dim':dimension,'head':head})
    models=[torch_architecture(p,{}) for _ in range(2)]
    with torch.no_grad():
        models[0].net[0].weight.fill_(.2);models[0].net[0].bias.copy_(torch.arange(dimension,dtype=torch.float32)*.1)
    models[1].load_state_dict(models[0].state_dict());models[1].to(device)
    values=[];gradients=[];states=[]
    target=np.asarray([0.,1.,0.,1.],np.float32) if kind=='failure_risk' else np.asarray([.15,.3,1.7,2.1],np.float32)
    for model,where in zip(models,['cpu',device]):
        x=torch.tensor([[-1.],[-.2],[.4],[1.]],device=where);y=torch.tensor(target,device=where)
        output=model(x)
        if kind=='quantiles':
            residual=y[:,None]-output;q=torch.tensor([.1,.5,.9],device=where)
            objective=torch.maximum(q*residual,(q-1)*residual).mean()
        else:objective=(output.reshape(-1)-y).square().mean()
        assert float(objective.detach().cpu())==pytest.approx(loss(kind,output.detach().cpu().numpy().reshape(-1) if dimension==1 else output.detach().cpu().numpy(),target,[.1,.5,.9]),rel=1e-5,abs=1e-6)
        optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001);optimizer.zero_grad();objective.backward()
        values.append(output.detach().cpu().numpy());gradients.append([v.grad.detach().cpu().numpy().copy() for v in model.parameters()]);optimizer.step()
        states.append([v.detach().cpu().numpy().copy() for v in model.parameters()])
    np.testing.assert_allclose(values[0],values[1],atol=1e-5,rtol=1e-4)
    for a,b in zip(gradients[0]+states[0],gradients[1]+states[1]):np.testing.assert_allclose(a,b,atol=1e-5,rtol=1e-4)
