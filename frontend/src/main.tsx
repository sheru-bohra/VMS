import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MsalProvider } from '@azure/msal-react';
import { App } from './app/App';
import { MsalAuthBridge } from './auth/MsalAuthBridge';
import { msalInstance } from './auth/msalInstance';
import { entraLoginEnabled, isEntraAuthMode, isVmsNativeAuthMode } from './config/auth';
import './styles/global.css';

const root = createRoot(document.getElementById('root')!);

if ((isEntraAuthMode || (isVmsNativeAuthMode && entraLoginEnabled)) && msalInstance) {
  msalInstance.initialize().then(() => {
    root.render(
      <StrictMode>
        <MsalProvider instance={msalInstance}>
          <MsalAuthBridge>
            <App />
          </MsalAuthBridge>
        </MsalProvider>
      </StrictMode>,
    );
  });
} else {
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
