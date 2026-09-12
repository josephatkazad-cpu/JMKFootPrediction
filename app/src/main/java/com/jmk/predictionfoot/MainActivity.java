package com.jmk.predictionfoot;

import android.app.*; import android.os.*; import android.content.*; import android.graphics.Color; import android.graphics.Typeface; import android.view.*; import android.widget.*;
import org.json.*; import java.text.*; import java.util.*;

public class MainActivity extends Activity {
    LinearLayout list; TextView status; String selectedDate;
    int dp(float v){return (int)(v*getResources().getDisplayMetrics().density+.5f);}
    TextView tv(String s,int size,boolean bold){ TextView t=new TextView(this); t.setText(s); t.setTextColor(Color.WHITE); t.setTextSize(size); t.setPadding(dp(4),dp(4),dp(4),dp(4)); if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD); return t; }
    @Override public void onCreate(Bundle b){super.onCreate(b); build(); load(0);}
    void build(){
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setPadding(dp(16),dp(12),dp(16),dp(8)); root.setBackgroundColor(Color.rgb(7,17,31));
        LinearLayout head=new LinearLayout(this); head.setOrientation(LinearLayout.HORIZONTAL); TextView title=tv("⚽ JMK Prediction Foot",22,true); head.addView(title,new LinearLayout.LayoutParams(0,dp(55),1));
        Button refresh=new Button(this); refresh.setText("↻"); refresh.setOnClickListener(v->load(selectedDate.equals(today())?0:1)); head.addView(refresh,new LinearLayout.LayoutParams(dp(55),dp(55))); root.addView(head);
        LinearLayout tabs=new LinearLayout(this); Button a=new Button(this), d=new Button(this); a.setText("Aujourd'hui"); d.setText("Demain"); tabs.addView(a,new LinearLayout.LayoutParams(0,dp(52),1)); tabs.addView(d,new LinearLayout.LayoutParams(0,dp(52),1)); root.addView(tabs);
        status=tv("Connexion au serveur…",13,false); status.setTextColor(Color.LTGRAY); root.addView(status);
        ScrollView sv=new ScrollView(this); list=new LinearLayout(this); list.setOrientation(LinearLayout.VERTICAL); sv.addView(list); root.addView(sv,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout nav=new LinearLayout(this); String[] ns={"Accueil","Matchs","Combiné","Compte"}; for(String n:ns){Button x=new Button(this);x.setText(n);nav.addView(x,new LinearLayout.LayoutParams(0,dp(54),1));} root.addView(nav);
        a.setOnClickListener(v->load(0)); d.setOnClickListener(v->load(1)); setContentView(root);
    }
    String today(){return new SimpleDateFormat("yyyy-MM-dd",Locale.US).format(new Date());}
    String datePlus(int n){Calendar c=Calendar.getInstance();c.add(Calendar.DATE,n);return new SimpleDateFormat("yyyy-MM-dd",Locale.US).format(c.getTime());}
    void load(int day){ selectedDate=datePlus(day); status.setText("Chargement des matchs du "+selectedDate+"…"); list.removeAllViews(); new Thread(()->{try{JSONObject j=ApiClient.get("/api/fixtures?date="+selectedDate); runOnUiThread(()->render(j));}catch(Exception e){runOnUiThread(()->{status.setText("Serveur indisponible"); TextView x=tv("Impossible de charger les matchs. Vérifie que le backend PythonAnywhere est en ligne.",15,false); x.setPadding(8,20,8,20); list.addView(x);});}}).start();}
    void render(JSONObject j){try{status.setText(j.optInt("total",0)+" match(s) réel(s) — données du serveur"); JSONArray arr=j.optJSONArray("matches"); if(arr==null||arr.length()==0){list.addView(tv("Aucun match trouvé pour cette date.",16,false));return;} String last=""; for(int i=0;i<arr.length();i++){JSONObject m=arr.getJSONObject(i);String country=m.optString("pays","Autre"),league=m.optString("championnat","Championnat"); if(!country.equals(last)){TextView h=tv("🌍 "+country+" — "+league,17,true); h.setPadding(0,dp(18),0,dp(8)); list.addView(h); last=country;} addMatch(m);} }catch(Exception e){status.setText("Réponse serveur invalide");}}
    void addMatch(JSONObject m){LinearLayout card=new LinearLayout(this);card.setOrientation(LinearLayout.VERTICAL);card.setPadding(dp(14),dp(12),dp(14),dp(12));card.setBackgroundColor(Color.rgb(15,30,48));String home=m.optJSONObject("domicile").optString("nom","Domicile"), away=m.optJSONObject("exterieur").optString("nom","Extérieur"); TextView teams=tv(home+"  vs  "+away,17,true); card.addView(teams); TextView info=tv("🕒 "+m.optString("horaire","--:--")+"   •   "+m.optString("statut",""),13,false);card.addView(info);Button b=new Button(this);b.setText("Analyser →");b.setOnClickListener(v->{Intent in=new Intent(this,AnalysisActivity.class);in.putExtra("fixture",m.optLong("fixture_id"));in.putExtra("home",home);in.putExtra("away",away);startActivity(in);});card.addView(b);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,LinearLayout.LayoutParams.WRAP_CONTENT);p.setMargins(0,0,0,dp(10));list.addView(card,p);}
}
