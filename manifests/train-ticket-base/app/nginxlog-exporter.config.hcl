listen {
  port = 4040
}

namespace "nginx" {
  format = "$remote_addr - $remote_user [$time_local] \"$request\" $request_length $status $body_bytes_sent $request_time \"$http_referer\" \"$http_user_agent\" \"$http_x_forwarded_for\" $upstream_response_time"

  relabel "request_path" {
    from = "request"
    split = 2
    separator = " "

    // if enabled, only include label in response count metric (default is false)
    only_counter = false

    match "^/api/v1/travelservice.*" {
      replacement = "/api/v1/travelservice"
    }
    match "^/api/v1/travel2service.*" {
      replacement = "/api/v1/travel2service"
    }
    match "^/api/v1/userservice/users.*" {
      replacement = "/api/v1/userservice/users"
    }
    match "^/api/v1/users/auth.*" {
      replacement = "/api/v1/users/auth"
    }
    match "^/api/v1/users/login.*" {
      replacement = "/api/v1/users/login"
    }
    match "^/api/v1/verifycode/generate.*" {
      replacement = "/api/v1/verifycode/generate"
    }
    match "^/api/v1/stationservice.*" {
      replacement = "/api/v1/stationservice"
    }
    match "^/api/v1/trainservice.*" {
      replacement = "/api/v1/trainservice"
    }
    match "^/api/v1/configservice.*" {
      replacement = "/api/v1/configservice"
    }
    match "^/api/v1/securityservice.*" {
      replacement = "/api/v1/securityservice"
    }
    match "^/api/v1/executeservice/execute/execute.*" {
      replacement = "/api/v1/executeservice/execute/execute"
    }
    match "^/api/v1/executeservice/execute/collected.*" {
      replacement = "/api/v1/executeservice/execute/collected"
    }
    match "^/api/v1/contactservice/contacts.*" {
      replacement = "/api/v1/contactservice/contacts"
    }
    match "^/api/v1/contactservice/contacts/account.*" {
      replacement = "/api/v1/contactservice/contacts/account"
    }
    match "^/api/v1/orderservice/order/refresh.*" {
      replacement = "/api/v1/orderservice/order/refresh"
    }
    match "^/api/v1/orderOtherService/orderOther/refresh.*" {
      replacement = "/api/v1/orderOtherService/orderOther/refresh"
    }
    match "^/api/v1/preserveservice/preserve.*" {
      replacement = "/api/v1/preserveservice/preserve"
    }
    match "^/api/v1/preserveotherservice/preserveOther.*" {
      replacement = "/api/v1/preserveotherservice/preserveOther"
    }
    match "^/price/query.*" {
      replacement = "/price/query"
    }
    match "^/price/queryAll.*" {
      replacement = "/price/queryAll"
    }
    match "^/price/create.*" {
      replacement = "/price/create"
    }
    match "^/price/delete.*" {
      replacement = "/price/delete"
    }
    match "^/price/update.*" {
      replacement = "/price/update"
    }
    match "^/basic/queryForTravel.*" {
      replacement = "/basic/queryForTravel"
    }
    match "^/ticketinfo/queryForTravel.*" {
      replacement = "/ticketinfo/queryForTravel"
    }
    match "^/notification/preserve_success.*" {
      replacement = "/notification/preserve_success"
    }
    match "^/notification/order_create_success.*" {
      replacement = "/notification/order_create_success"
    }
    match "^/notification/order_changed_success.*" {
      replacement = "/notification/order_changed_success"
    }
    match "^/api/v1/inside_pay_service/inside_payment.*" {
      replacement = "/api/v1/inside_pay_service/inside_payment"
    }
    match "^/payment/pay.*" {
      replacement = "/payment/pay"
    }
    match "^/payment/addMoney.*" {
      replacement = "/payment/addMoney"
    }
    match "^/payment/query.*" {
      replacement = "/payment/query"
    }
    match "^/rebook.*" {
      replacement = "/rebook"
    }
    match "^/api/v1/cancelservice/cancel.*" {
      replacement = "/api/v1/cancelservice/cancel"
    }
    match "^/api/v1/cancelservice/cancel/refound.*" {
      replacement = "/api/v1/cancelservice/cancel/refound"
    }
    match "^/api/v1/stationservice/stations/name.*" {
      replacement = "/api/v1/stationservice/stations/name"
    }
    match "^/api/v1/rebookservice/rebook.*" {
      replacement = "/api/v1/rebookservice/rebook"
    }
    match "^/api/v1/rebookservice/rebook/difference.*" {
      replacement = "/api/v1/rebookservice/rebook/difference"
    }
    match "^/route/createAndModify.*" {
      replacement = "/route/createAndModify"
    }
    match "^/route/delete.*" {
      replacement = "/route/delete"
    }
    match "^/route/queryAll.*" {
      replacement = "/route/queryAll"
    }
    match "^/route/queryById/.*" {
      replacement = "/route/queryById/:id"
    }
    match "^/route/queryByStartAndTerminal.*" {
      replacement = "/route/queryByStartAndTerminal"
    }
    match "^/api/v1/assuranceservice/assurances/types.*" {
      replacement = "/api/v1/assuranceservice/assurances/types"
    }
    match "^/assurance/getAssuranceById/.*" {
      replacement = "/assurance/getAssuranceById/:id"
    }
    match "^/assurance/findAssuranceByOrderId/.*" {
      replacement = "/assurance/findAssuranceByOrderId/:id"
    }
    match "^/assurance/findAll.*" {
      replacement = "/assurance/findAll"
    }
    match "^/assurance/create.*" {
      replacement = "/assurance/create"
    }
    match "^/assurance/deleteAssurance.*" {
      replacement = "/assurance/deleteAssurance"
    }
    match "^/assurance/deleteAssuranceByOrderId/.*" {
      replacement = "/assurance/deleteAssuranceByOrderId/:id"
    }
    match "^/assurance/modifyAssurance.*" {
      replacement = "/assurance/modifyAssurance"
    }
    match "^/office/getRegionList.*" {
      replacement = "/office/getRegionList"
    }
    match "^/office/getAll.*" {
      replacement = "/office/getAll"
    }
    match "^/office/getSpecificOffices.*" {
      replacement = "/office/getSpecificOffices"
    }
    match "^/office/addOffice.*" {
      replacement = "/office/addOffice"
    }
    match "^/office/deleteOffice.*" {
      replacement = "/office/deleteOffice"
    }
    match "^/office/updateOffice.*" {
      replacement = "/office/updateOffice"
    }
    match "^/travelPlan/getTransferResult.*" {
      replacement = "/travelPlan/getTransferResult"
    }
    match "^/api/v1/travelplanservice/travelPlan/cheapest.*" {
      replacement = "/api/v1/travelplanservice/travelPlan/cheapest"
    }
    match "^/api/v1/travelplanservice/travelPlan/quickest.*" {
      replacement = "/api/v1/travelplanservice/travelPlan/quickest"
    }
    match "^/api/v1/travelplanservice/travelPlan/minStation.*" {
      replacement = "/api/v1/travelplanservice/travelPlan/minStation"
    }
    match "^/api/v1/consignservice/consigns.*" {
      replacement = "/api/v1/consignservice/consigns"
    }
    match "^/api/v1/consignservice/consigns/account.*" {
      replacement = "/api/v1/consignservice/consigns/account"
    }
    match "^/getVoucher.*" {
      replacement = "/getVoucher"
    }
    match "^/routePlan/minStopStations.*" {
      replacement = "/routePlan/minStopStations"
    }
    match "^/routePlan/cheapestRoute.*" {
      replacement = "/routePlan/cheapestRoute"
    }
    match "^/routePlan/quickestRoute.*" {
      replacement = "/routePlan/quickestRoute"
    }
    match "^/api/v1/foodservice.*" {
      replacement = "/api/v1/foodservice"
    }
    match "^/api/v1/foodservice/foods.*" {
      replacement = "/api/v1/foodservice/foods"
    }
    match "^/food/createFoodOrder.*" {
      replacement = "/food/createFoodOrder"
    }
    match "^/food/cancelFoodOrder.*" {
      replacement = "/food/cancelFoodOrder"
    }
    match "^/food/updateFoodOrder.*" {
      replacement = "/food/updateFoodOrder"
    }
    match "^/food/findAllFoodOrder.*" {
      replacement = "/food/findAllFoodOrder"
    }
    match "^/food/findFoodOrderByOrderId/.*" {
      replacement = "/food/findFoodOrderByOrderId/:id"
    }
    match "^/news-service/news.*" {
      replacement = "/news-service/news"
    }
    match "^/api/v1/adminbasicservice/adminbasic/contacts.*" {
      replacement = "/api/v1/adminbasicservice/adminbasic/contacts"
    }
    match "^/api/v1/adminbasicservice/adminbasic/stations.*" {
      replacement = "/api/v1/adminbasicservice/adminbasic/stations"
    }
    match "^/api/v1/adminbasicservice/adminbasic/trains.*" {
      replacement = "/api/v1/adminbasicservice/adminbasic/trains"
    }
    match "^/api/v1/adminbasicservice/adminbasic/prices.*" {
      replacement = "/api/v1/adminbasicservice/adminbasic/prices"
    }
    match "^/api/v1/adminbasicservice/adminbasic/configs.*" {
      replacement = "/api/v1/adminbasicservice/adminbasic/configs"
    }
    match "^/api/v1/adminorderservice/adminorder.*" {
      replacement = "/api/v1/adminorderservice/adminorder"
    }
    match "^/api/v1/adminrouteservice/adminroute.*" {
      replacement = "/api/v1/adminrouteservice/adminroute"
    }
    match "^/api/v1/admintravelservice/admintravel.*" {
      replacement = "/api/v1/admintravelservice/admintravel"
    }
    match "^/api/v1/adminuserservice/users.*" {
      replacement = "/api/v1/adminuserservice/users"
    }
    match "^/api/v1/avatar.*" {
      replacement = "/api/v1/avatar"
    }
  }

  source = {
    files = [
      "/etc/nginxlog/access.log"
    ]
  }

  print_log = true

  histogram_buckets = [.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
}
