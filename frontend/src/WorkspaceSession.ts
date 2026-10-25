import { createContext } from 'react';
export const WorkspaceSession = createContext({ name: 'Local workspace', protected: false, signOut: () => {} });
