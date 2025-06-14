import Head from 'next/head';
import Script from 'next/script';

export default function Home() {
  return (
    <>
      <Head>
        <meta charSet="UTF-8" />
        <meta name="viewport" content="width=device-width" />
        <link rel="stylesheet" href="/css/index.css" />
        <title>glTF Viewer</title>
      </Head>
      <div id="gltf-container" className="top_bar_container">
        <div className="full-width">
          <h1 className="title">glTF Viewer</h1>
          <div className="full-width top-nav-icons-container">
            <div className="top-nav-icons">
              <img id="download-gltf" src="/images/download-button.svg" />
            </div>
            <div className="top-nav-icons">
              <a href="https://github.com/onshape-public/app-gltf-viewer#readme" target="_blank">
                <img src="/images/help-button.svg" />
              </a>
            </div>
          </div>
        </div>
        <select id="elem-selector" className="select-container">
          <option value="">Select an Element</option>
        </select>
      </div>
      <div id="gltf-viewport"></div>
      <Script src="/js/index.js" type="module" />
    </>
  );
}
