"""Differentiable attack surrogates bound to the actual analytical output."""
from ..contracts import EvaluationError


def bound_channel(raw, spec, channel, tolerance):
    """Replay the admitted point/probability binding without detaching its graph."""
    import torch
    binding=next((b for b in spec.outputs if b.channel==channel),None)
    if binding is None:
        raise EvaluationError('Attack requires a declared differentiable point or probability channel.','gradient_unavailable')
    if isinstance(raw,dict):value=raw.get(binding.source)
    elif binding.source=='output':value=raw
    else:value=None
    if not isinstance(value,torch.Tensor) or not value.is_floating_point() or not value.requires_grad:
        raise EvaluationError('The bound output has no admitted differentiable tensor path.','gradient_unavailable')
    if value.ndim==1:value=value[:,None]
    if value.ndim!=2 or value.shape[0]!=1:
        raise EvaluationError('Attack output requires one aligned scalar/vector row.','gradient_unavailable')
    if binding.indices:
        if max(binding.indices)>=value.shape[1]:
            raise EvaluationError('Attack output indices differ from the bound tensor.','gradient_unavailable')
        value=value[:,list(binding.indices)]
    if binding.activation=='softmax':value=torch.softmax(value,dim=1)
    elif binding.activation=='sigmoid':value=torch.sigmoid(value)
    if not torch.isfinite(value).all():
        raise EvaluationError('The bound attack output is nonfinite.','gradient_unavailable')
    if channel=='point':
        if value.numel()!=1:
            raise EvaluationError('Attack point binding must identify one scalar.','gradient_unavailable')
        return value.reshape(())
    classes=binding.classes
    if value.shape[1]!=len(classes):
        raise EvaluationError('Attack probability class dimensions differ.','gradient_unavailable')
    if len(classes)==1 and spec.task.kind=='binary_classification':
        value=torch.cat([value if c==classes[0] else 1-value for c in spec.task.classes],dim=1)
    elif set(classes)==set(spec.task.classes):
        value=value[:,[classes.index(c) for c in spec.task.classes]]
    else:
        raise EvaluationError('Attack requires complete bound probability semantics.','gradient_unavailable')
    if torch.any(value<0) or torch.any(value>1) or torch.abs(value.sum()-1)>tolerance:
        raise EvaluationError('The bound attack probabilities are invalid.','gradient_unavailable')
    return value[0]


def attack_objective(raw, spec, attack, event, baseline, tolerance):
    """Named-channel surrogate; final success always uses complete normal replay.

    Increasing the bound point remains the registered directional surrogate for
    absolute output change. Squared error and log probability are smooth
    monotone surrogates for the declared loss/target objectives.
    """
    import torch
    if spec.task.kind=='regression':
        point=bound_channel(raw,spec,'point',tolerance)
        if attack.objective=='output_change':value=point
        elif attack.objective=='loss_increase' and event['truth']['valid']:
            value=(point-float(event['truth']['value'])).square()
        else:
            raise EvaluationError('Regression gradient objective lacks an admitted target.','gradient_unavailable')
    else:
        probabilities=bound_channel(raw,spec,'probabilities',tolerance)
        from .attacks import decision
        target=attack.target_class if attack.objective=='targeted' else event['truth']['value'] if attack.objective=='misclassification' and event['truth']['valid'] else decision(baseline,spec.task)
        if attack.objective not in {'output_change','misclassification','targeted'} or target not in spec.task.classes:
            raise EvaluationError('Classification gradient objective lacks an admitted target.','gradient_unavailable')
        value=torch.log(probabilities[spec.task.classes.index(target)])
        if attack.objective!='targeted':value=-value
    if not torch.isfinite(value):
        raise EvaluationError('The exact bound gradient surrogate is nonfinite.','gradient_unavailable')
    return value


def input_gradient(objective, tensor):
    import torch
    gradient=torch.autograd.grad(objective,tensor,allow_unused=True)[0]
    if gradient is None or not torch.isfinite(gradient).all():
        raise EvaluationError('The bound objective has no finite input gradient.','gradient_unavailable')
    return gradient.detach().cpu().numpy()[0]
