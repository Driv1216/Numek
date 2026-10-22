import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../foundation/base.css';
import Landing from './Landing';

const page = document.body.dataset.page === 'datatrust' ? 'datatrust' : 'numek';
createRoot(document.getElementById('root')!).render(<StrictMode><Landing page={page} /></StrictMode>);
