import { JupyterFrontEnd } from '@jupyterlab/application';
import React from 'react';

export const JupyterLabAppContext = React.createContext<JupyterFrontEnd | undefined>(undefined);
export const EXTENSION_ID = 'spark-connect-labextension';
export const FRONTEND_COMM_ID = `${EXTENSION_ID}:comm:frontend`;
