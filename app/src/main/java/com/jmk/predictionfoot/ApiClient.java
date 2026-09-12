package com.jmk.predictionfoot;

import org.json.JSONObject;
import java.io.*; import java.net.*; import java.nio.charset.StandardCharsets;

public final class ApiClient {
    public static final String BASE_URL = "https://josephatkazad2013.pythonanywhere.com";
    private ApiClient() {}
    public static JSONObject get(String path) throws Exception {
        URL url = new URL(BASE_URL + path); HttpURLConnection c=(HttpURLConnection)url.openConnection();
        c.setRequestMethod("GET"); c.setConnectTimeout(12000); c.setReadTimeout(20000); c.setRequestProperty("Accept","application/json");
        int code=c.getResponseCode(); InputStream in=code>=200&&code<400?c.getInputStream():c.getErrorStream();
        StringBuilder s=new StringBuilder(); if(in!=null){BufferedReader r=new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8)); String line; while((line=r.readLine())!=null)s.append(line); r.close();}
        if(code<200||code>=300) throw new IOException("HTTP "+code+": "+s);
        return new JSONObject(s.toString());
    }
}
