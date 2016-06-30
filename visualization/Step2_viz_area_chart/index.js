
var format = d3.time.format("%Y");

var margin = {top: 100, right: 225, bottom: 100, left: 40},
    margin2 = {top: 730, right: 225, bottom: 20, left: 40},
    width = 1500 - margin.left - margin.right,
    height = 800 - margin.top - margin.bottom,
    height2 = 800 - margin2.top - margin2.bottom;

var x = d3.time.scale().range([0, width]),
    x2 = d3.time.scale().range([0, width]),
    y = d3.scale.linear().range([height, 0]),
    y2 = d3.scale.linear().range([height2, 0]);

var hoveredColorValue;
var hoveredStrokeColor = "black";

var z = d3.scale.ordinal()
                      // .range(["#A67746","#B0E3F7","#48ADD4","#BED99F","#508811",
                      // "#DA817E","#A03835","#E6E473","#A2A2A2","#BAEED0",
                      // "#40A77C","#8A3BC4","#CDABE6","#787D2E","#CACF79",
                      // "#5A7899","#A9BFD6","#A54188","#BF87AF"]);


                  .range(["#a50026",
                  "#d73027",
                  "#f46d43",
                  "#fdae61",
                  "#fee090",
                  "#ffffbf",
                  "#e0f3f8",
                  "#abd9e9",
                  "#74add1",
                  "#4575b4",
                  "#313695",
                  "#d9ef8b",
"#a6d96a",
"#66bd63",
"#1a9850",
"#006837",
"#8c510a",
"#bf812d",
"#dfc27d"]);


// E55937
// var colorLegendG = focus.append("g")
//         .attr("class", "color-legend")5ABC83
//         .attr("transform", "translate(16, 2)");


var xAxis = d3.svg.axis().scale(x).orient("bottom"),
    xAxis2 = d3.svg.axis().scale(x2).orient("bottom"),
    yAxis = d3.svg.axis().scale(y).orient("left");

var brush = d3.svg.brush()
    .x(x2)
    .on("brush", brushed);

var area2 = d3.svg.area()
    .interpolate("monotone")
    .x(function(d) { return x2(d.date); })
    .y0(height2)
    .y1(function(d) { return y2(d.value); });

var stack = d3.layout.stack()
    .offset("zero")
    .values(function(d) { return d.values; })
    .x(function(d) { return d.date; })
    .y(function(d) { return d.value; });

var area = d3.svg.area()
    .interpolate("basis")
    .x(function(d) { return x(d.date); })
    .y0(function(d) { return y(d.y0); })
    .y1(function(d) { return y(d.y0 + d.y); });

// var colorLegend = d3.legend.color()
//         .scale(z)
//         .shapePadding(3)
//         .shapeWidth(15)
//         .shapeHeight(15)
//         .labelOffset(4)
//         .ascending(true);

var tooltip = d3.select("body")
    .append("div")
    .attr("class", "tooltip")
    .style("position", "absolute")
    .style("z-index", "10")
    .style("visibility", "hidden");


var svg = d3.select("body").append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom);

svg.append("defs").append("clipPath")
    .attr("id", "clip")
  .append("rect")
    .attr("width", width)
    .attr("height", height);

var focus = svg.append("g")
    .attr("class", "focus")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

var context = svg.append("g")
    .attr("class", "context")
    .attr("transform", "translate(" + margin2.left + "," + margin2.top + ")");

console.log("before queue")

d3_queue.queue()
    .defer(d3.csv, "year_data.csv")
    .defer(d3.csv, "year_topic_data2.csv")
    .awaitAll(draw);
console.log("After queue")

function draw(error, data) {
  if (error) throw error;
  console.log("here")
  yearData = data[0];
  topicData = data[1];
    console.log(yearData);

  yearData.forEach(function(d) {
    d.date = format.parse(d.date);
    d.value = +d.value;
  });
  console.log("here")

  topicData.forEach(function(d) {
    d.date = format.parse(d.date);
    d.value = +d.value;
    d.key = d.key;
    d.title = d.title;
    d.leadpp = d.leadpp;
    d.words = d.topicwords;
    d.url = d.exampleURL;
  });
  console.log("here")

  console.log(topicData);

  var nestStack = d3.nest()
      .key(function(d) { return d.key; })
      .entries(topicData);

  var layers = stack(nestStack);

  console.log(layers);
console.log("here1")

  x.domain(d3.extent(yearData.map(function(d) { return d.date; })));
  x2.domain(x.domain());
  y.domain([0, d3.max(topicData, function(d) { return d.y0 + d.y; })]);
  y2.domain([0, d3.max(yearData.map(function(d) { return d.value; }))]); 

  context.append("path")
      .datum(yearData)
      .attr("class", "area")
      .attr("d", area2);

  context.append("g")
      .attr("class", "x axis")
      .attr("transform", "translate(0," + height2 + ")")
      .call(xAxis2);

  context.append("g")
      .attr("class", "x brush")
      .call(brush)
    .selectAll("rect")
      .attr("y", -6)
      .attr("height", height2 + 7);

  context.append("text")
                    .attr("x", 80)
                    .attr("y", 35)
                    .style("fill", '#555555')
                    .text("Drag cursor here to zoom")
                    .style("font-size", 15)
                    .style("text-anchor", 'middle');


  var addTooltip = function(d) {
   tooltip.html("");
   tooltip.append("h3").attr("class", "tooltip_title");
   tooltip.append("pre").attr("class", "tooltip_body");
   tooltip.select(".tooltip_title")
     .text(d.key)

  topicData = d.values[0];
  html = "Example Case: " + "\n" + "<i><b>" + topicData.title + "</b></i>"+ "\n";
  html += topicData.leadpp + "..." + "<a href=" + topicData.url + " target='_blank'>" + "[READ MORE]"+ "</a>" + "\n\n\n\n"
  html += "Topic Words: " + "\n" + topicData.topicwords + "\n";
  

   tooltip.select(".tooltip_body").html(html);
    //   "Topic Words: " + d.words + "\n"
    // );

    // tooltip.select(".tooltip_body")
    // .html(
    //                    " - <a href=" + d.url +
    //                   " target='_blank'>" +d.title+ "</a>"
    //               )
    // tooltip.select(".tooltip_body")
    //   .text(
    //    "Example: " + d.title + "\n"
    //    + d.leadpp
    //   );




   return tooltip.style("visibility", "visible");
  }
console.log("tooltip");


  focus.selectAll(".layer")
      .data(layers)
    .enter().append("path")
      .attr("class", "layer")
      .attr("d", function(d) { return area(d.values); })
      .style("fill", function(d, i) { return z(d.key); })
      .on("click", function(d) {
        d3.selectAll(".layer").attr("opacity", 0.3);
        d3.select(this)
          .style("fill", "black")
          .attr("opacity", 1);
        addTooltip(d);
        //tooltip.style("top", (d3.event.pageY-52) + "px").style("left", (d3.event.pageX+18) + "px");
        tooltip.style("top", 15 + "px").style("left", 65 + "px");
          d3.event.stopPropagation();
      })
     // .on("mousemove", function() {
     //   return tooltip.style("top", (d3.event.pageY-52) + "px").style("left", (d3.event.pageX+18) + "px");
     // })
      // .on("mouseout", function(d) {
      //   d3.selectAll(".layer").attr("opacity", 1);
      //  return tooltip.style("visibility", "hidden");
      // });
  svg.on("click", function() {
        d3.selectAll(".layer").attr("opacity", 1)
                              .style("fill", function(d, i) { return z(d.key); });
        tooltip.style("visibility", "hidden");
        
  })
console.log("here2")



  focus.append("g")
      .attr("class", "x axis")
      .attr("transform", "translate(0," + height + ")")
      .call(xAxis);

  focus.append("g")
      .attr("class", "y axis")
      .call(yAxis);

focus.append("text")
                    .attr("x", width / 2)
                    .attr("y", 20)
                    .style("fill", '#555555')
                    .text("Supreme Court Topics Over Time")
                    .style("font-size", 32)
                    .style("text-anchor", 'middle');

focus.append("text")
                    // .attr("x", 15)
                    // .attr("y", 8)
                    .attr("dy", "1.14em")
                    .attr("transform", "rotate(-90)")
                    .style("fill", '#555555')
                    .text("Number of Cases")
                    .style("font-size", 10)
                    .style("text-anchor", 'end');                    

focus.append("text")
                    .attr("x", width / 2)
                    .attr("y", 40)
                    .style("fill", '#555555')
                    .text("(click the graph for details)")
                    .style("font-size", 15)
                    .style("text-anchor", 'middle');                    

svg.append("g")
  .attr("class", "legendOrdinal")
  .attr("transform", "translate(" + [width + margin.left + 25, margin.top] + ")");

var legendOrdinal = d3.legend.color()
  .shape("path", d3.svg.symbol().type("square").size(150)())
  .shapePadding(10)
  .scale(z);
  //.text(d.key);

svg.select(".legendOrdinal")
  .call(legendOrdinal);



};

function brushed() {
  x.domain(brush.empty() ? x2.domain() : brush.extent());
  focus.selectAll(".layer").attr("d", function(d) { return area(d.values); })
  focus.select(".x.axis").call(xAxis);
}

