from dataclasses import replace
import csv
import numpy as np
import pytest

from confidenceguard import (FeatureField,OutputBinding,DeviceSpec,ExecutionLimits,AuxiliaryStudySpec,AuxiliaryCandidate,
    execute_predictor,fit_auxiliary,apply_auxiliary,RobustnessSpec,ScenarioSpec,TransformationSpec,AttackSpec,run_robustness)
from confidenceguard.execution.adapters import torch_architecture
from .helpers import execution,file,CFG


def save_model(p,path):
    import torch
    from safetensors.torch import save_file
    model=torch_architecture(p,{})
    with torch.no_grad():
        for name,value in model.named_parameters():value.fill_(.1)
        final=model.net[-1] if hasattr(model.net,'__getitem__') else model.net
        if final.weight.shape[0]==2:final.weight[0].fill_(-.1);final.weight[1].fill_(.1)
    save_file(model.state_dict(),str(path));path.chmod(0o600)
    return replace(p,adapter='torch',files=(file(path),),entry=path.name)


def change_input(s,value):
    path=s.sources[0].path
    with open(path) as stream:records=list(csv.DictReader(stream))
    for i,r in enumerate(records):r['x']=value(i)
    with open(path,'w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)


def test_keyed_vectors_fitting_and_tensor_attack(tmp_path):
    s=execution(tmp_path,regression=True,n=40);matrix=tmp_path/'vectors.npy'
    np.save(matrix,np.asarray([[i/40,i%3] for i in range(40)],np.float32),allow_pickle=False)
    p=replace(s.predictors[0],preprocessing={'kind':'tensor','tensor_file':str(matrix),'keys_source':s.sources[0].path,'key_columns':['id']},architecture={'kind':'mlp','input_dim':2,'hidden':[],'output_dim':1})
    p=save_model(p,tmp_path/'vector.safetensors');s=replace(s,predictors=(p,))
    r=execute_predictor(s,CFG)
    assert all(isinstance(o['input_record']['x'],list) and len(o['input_record']['x'])==2 for o in r.private['output_rows'])
    fitted=fit_auxiliary(AuxiliaryStudySpec(s,'scale','model',candidates=(AuxiliaryCandidate('constant','constant'),)),CFG)
    a=fitted.private['auxiliary_artifacts'][0]
    assert a['target']['vector_field']=='x'
    assert apply_auxiliary(s,a,CFG,role='E').data['measurements']
    scenario=ScenarioSpec('vector_stress',(TransformationSpec('round','round',('x',),parameters={'step':.1},stage='tensor'),),
        attack=AttackSpec('fgsm',('x',),access='white_box',stage='tensor',epsilon=.1,queries_per_root=4))
    stressed=run_robustness(RobustnessSpec(s,(scenario,),role='E'),CFG)
    assert any(o.get('variant',{}).get('attack',{}).get('gradient_steps')==1 for o in stressed.private['output_rows'])


@pytest.mark.parametrize('kind',['text','image'])
@pytest.mark.parametrize('device',['cpu','mps','cuda'])
def test_offline_modalities_and_unknown_outcomes(tmp_path,kind,device):
    import torch
    if device=='mps' and not torch.backends.mps.is_available():pytest.skip('not_run_hardware_unavailable: real MPS access required')
    if device=='cuda' and not torch.cuda.is_available():pytest.skip('not_run_hardware_unavailable: real NVIDIA access required for CUDA modalities')
    s=execution(tmp_path,n=8);base=s.predictors[0]
    outputs=(OutputBinding('logits',classes=('no','yes')),OutputBinding('probabilities',classes=('no','yes'),activation='softmax'))
    if kind=='text':
        from tokenizers import Tokenizer,models,pre_tokenizers
        tokenizer=Tokenizer(models.WordLevel({'[UNK]':0,'[PAD]':1,'yes':2,'no':3,'word':4},unk_token='[UNK]'));tokenizer.pre_tokenizer=pre_tokenizers.Whitespace()
        path=tmp_path/'tokenizer.json';tokenizer.save(str(path));path.chmod(0o600)
        change_input(s,lambda i:'yes word '*10)
        p=replace(base,inputs=(FeatureField('x','x','text',role='model_input'),),outputs=outputs,architecture={'kind':'text','vocabulary':5,'embedding_dim':4,'output_dim':2},preprocessing={'kind':'text','tokenizer':path.name,'padding_id':1})
        p=save_model(p,tmp_path/'text.safetensors');p=replace(p,files=(*p.files,file(path)))
        scenario=ScenarioSpec('unicode',(TransformationSpec('unicode','text_unicode',('x',),parameters={'form':'NFKC'}),))
    else:
        from PIL import Image
        path=tmp_path/'image.png';Image.fromarray(np.full((16,16,3),128,np.uint8)).save(path)
        change_input(s,lambda i:path.name)
        p=replace(base,inputs=(FeatureField('x','x','asset',role='model_input'),),outputs=outputs,architecture={'kind':'cnn','channels':3,'output_dim':2},preprocessing={'kind':'image','image_size':[8,8]})
        p=save_model(p,tmp_path/'image.safetensors')
        scenario=ScenarioSpec('pixel_attack',attack=AttackSpec('pgd',('x',),access='white_box',stage='canonical_image',epsilon=.1,steps=2,restarts=1,queries_per_root=8))
    s=replace(s,predictors=(p,),device=DeviceSpec(device),limits=replace(s.limits,max_tokens=8))
    result=run_robustness(RobustnessSpec(s,(scenario,),role='E'),CFG)
    variants=[o for o in result.private['output_rows'] if 'variant' in o]
    assert variants and all(not o['truth']['valid'] for o in variants)
    assert result.data['cg6']['devices']['model']['kind']==device
    if kind=='text':assert result.data['cg6']['devices']['model']['text_coverage']['truncated_events']>0
    else:
        assert all(o['variant']['attack']['gradient_steps']==2 for o in variants)
        assert result.private['variant_assets']
