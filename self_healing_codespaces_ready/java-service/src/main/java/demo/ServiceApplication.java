package demo;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.context.annotation.Bean;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Counter;
@SpringBootApplication
@RestController
public class ServiceApplication {
 private static final Logger log=LoggerFactory.getLogger(ServiceApplication.class);
 private final AtomicBoolean broken=new AtomicBoolean(false);
 @Value("${SERVICE_NAME:orders}") String name;
 @Value("${INVENTORY_URL:http://localhost:8082}") String inventory;
 @Value("${PAYMENT_URL:http://localhost:8083}") String payments;
 private final RestTemplate http=new RestTemplate();
 private final MeterRegistry registry;
 public ServiceApplication(MeterRegistry registry){this.registry=registry; io.micrometer.core.instrument.Gauge.builder("demo_fault",broken, b -> b.get()?1:0).register(registry);}
 public static void main(String[] args){SpringApplication.run(ServiceApplication.class,args);}
 @Bean HealthIndicator demoHealth(){return () -> broken.get()?Health.down().withDetail("fault","injected").build():Health.up().build();}
 @GetMapping("/") Map<String,Object> root(){return Map.of("service",name,"status",broken.get()?"DOWN":"UP");}
 @GetMapping("/check") ResponseEntity<?> check(@RequestHeader(value="X-Request-ID",required=false) String id){
   if(broken.get()) {log.error("requestId={} service={} failure=INJECTED",id,name);return ResponseEntity.status(503).body(Map.of("error","injected fault"));}
   log.info("requestId={} service={} status=OK",id,name);return ResponseEntity.ok(Map.of("service",name,"status","OK"));
 }
 @PostMapping("/fault/on") Map<String,String> faultOn(){broken.set(true);log.error("service={} fault enabled",name);return Map.of("fault","enabled");}
 @PostMapping("/fault/off") Map<String,String> faultOff(){broken.set(false);return Map.of("fault","disabled");}
 @PostMapping("/order") ResponseEntity<?> order(@RequestBody Map<String,Object> payload){
  if(!name.equals("orders"))return ResponseEntity.status(404).build();
  String id=UUID.randomUUID().toString();
  try {
   if(broken.get())throw new RuntimeException("orders unavailable");
   for(String url:List.of(inventory,payments)){
    ResponseEntity<String> r=http.exchange(url+"/check",HttpMethod.GET,new HttpEntity<>(new HttpHeaders(){{set("X-Request-ID",id);}}),String.class);
    if(!r.getStatusCode().is2xxSuccessful())throw new RuntimeException(url+" unavailable");
   }
   Counter.builder("demo_orders_total").tag("result","success").register(registry).increment();
   log.info("requestId={} order={} status=SUCCESS",id,payload);
   return ResponseEntity.ok(Map.of("orderId",id,"status","CONFIRMED"));
  }catch(Exception ex){Counter.builder("demo_orders_total").tag("result","failure").register(registry).increment();log.error("requestId={} order failed",id,ex);return ResponseEntity.status(503).body(Map.of("requestId",id,"status","FAILED"));}
 }
}
