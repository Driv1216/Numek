// The NUMEK product registry, shared by the marketing site and the local app. DataTrust is the only
// available product; ConfidenceGuard and HallucinationGuard appear as status only.
export type ProductId = 'dt' | 'cg' | 'hg';
export const products: { id: ProductId; name: string; moment: string; status: string; statusTone: 'on' | 'dev' | 'res'; line: string }[] = [
  { id: 'dt', name: 'DataTrust', moment: 'Before training', status: 'Available', statusTone: 'on', line: 'Dataset reliability for the data AI learns from.' },
  { id: 'cg', name: 'ConfidenceGuard', moment: 'During deployment', status: 'In development · CG1 implemented, awaiting review', statusTone: 'dev', line: 'Model reliability from the predictions it makes.' },
  { id: 'hg', name: 'HallucinationGuard', moment: 'After generation', status: 'Research direction · placeholder', statusTone: 'res', line: 'Grounding for the answers it writes.' },
];
