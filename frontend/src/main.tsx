import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import AccessBoundary from './AccessBoundary';
import './style.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><AccessBoundary><App /></AccessBoundary></React.StrictMode>);
