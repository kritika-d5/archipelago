import React, { useEffect } from 'react';

function ConnectCallback() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    const toolkit = params.get('toolkit') || 'github';
    if (status === 'success' && window.opener) {
      window.opener.postMessage({ type: toolkit === 'notion' ? 'NOTION_CONNECTED' : 'COMPOSIO_CONNECTED' }, window.location.origin);
    }
    window.close();
  }, []);
  return (
    <div style={{ padding: '2rem', textAlign: 'center', fontFamily: 'system-ui' }}>
      <p>Connection complete. This window will close automatically.</p>
    </div>
  );
}

export default ConnectCallback;
