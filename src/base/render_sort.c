#include "common.h"
typedef struct {s16 rotation[3][3];s16 pad;vec3d_t vector;} render_matrix_t;
extern void RotMatrix(void *,void *);
extern void GsGetLs(void *,void *);
extern void GsGetLws(void *,void *,void *);
extern void GsSetLightMatrix(void *);
extern void GsSetLsMatrix(void *);
extern void GsSortBg(void *,s32,u16);
extern void GsSortBoxFill(void *,s32,u16);
extern void GsSortSprite(void *,s32,u16);
extern void linked_list_next(void **,s32 *);
extern void func_80018464(void *,s32,s32,void *);
extern void func_8001EE98(vec3d_t *,void *,s32,void *);
#define BP(p,off) (*(u8 **)((u8 *)(p)+(off)))
#define WP(p,off) (*(s32 *)((u8 *)(p)+(off)))
#define HP(p,off) (*(s16 *)((u8 *)(p)+(off)))
#define UP(p,off) (*(u16 *)((u8 *)(p)+(off)))
#define OT(p) WP((WP(p,0x74)<<2)+(s32)(p),0x78)
static inline void sort_child_next(u8 *object,u8 **child,s32 *cursor){
 u8 *temp;
 do{
  if(*child==NULL)*cursor=WP(object,4);
  linked_list_next((void **)child,cursor);
  temp=*child;
  if(temp!=NULL && (WP(BP(temp,0),0)&0xF)==4 && BP(temp,0xC)==object)break;
  if(*cursor==0){*child=NULL;break;}
 }while(1);
}
typedef struct {u32 attributes; s16 x,y;u16 width,height;u8 r,g,b,pad;} sort_box_fill_t;
typedef struct {u8 base[0x44];u16 depth,reserved;s32 relative;s32 color;s32 x,y;sort_box_fill_t fill;} sort_box_t;
typedef struct {u32 attributes;s16 x,y;u16 width,height,tpage;u8 u,v;u16 cx,cy;u8 r,g,b,pad;s16 mx,my;s32 scalex,scaley,rotation;} sort_sprite_t;
typedef struct {u8 base[0x64];sort_sprite_t sprite;u8 extra[0x14];s32 percentage_x,percentage_y;} sort_screen_t;
/* Visibility flags use the sign bit for a hidden object. */
static inline s32 sort_is_visible(u8 *object){return WP(object,0x10)>=0;}
/* Recursively sort visible models, boxes, backgrounds and sprites. */
void func_80012064(u8 *renderer,u8 *object){
 render_matrix_t view;
 render_matrix_t light;
 render_matrix_t *viewp,*lightp;
 u8 *child;
 s32 cursor;
 s32 transformed=0;
 u8 *coords;
 s16 *row;
 s16 *end;
 s32 *scale;
 s32 kind;
 sort_sprite_t *sprite;
 viewp=&view;lightp=&light;
 if(*BP(object,0)==0x24 && !sort_is_visible(object))return;
 coords=BP(object,0x14);
 row=(s16 *)(coords+4);
 if(WP(coords,0)==0){
  scale=(s32 *)BP(coords,0x44);
  transformed=1;
  end=(s16 *)(coords+0x16);
  RotMatrix(scale+4,row);
  while((u32)row<(u32)end){
   *row=(u32)(*row * *scale++)>>12;row++;
   *row=(u32)(*row * *scale++)>>12;row++;
   *row=(u32)(*row * *scale)>>12;row++;
   scale-=2;
  }
 }
 child=NULL;
 do{
  sort_child_next(object,&child,&cursor);
  if(child!=NULL){
   if(transformed)WP(BP(child,0x14),0)=0;
   func_80012064(renderer,child);
  }
 }while(cursor!=0);
 kind=WP(BP(object,0),0);
 if((kind&0xFF)==0x54){
  GsSortBg(object+0x44,OT(renderer),(1<<WP(renderer,0x3C))-1);
  return;
 }
 if((kind&0xFF)==0x64){
  sort_box_t *box=(sort_box_t *)object;
  if(box->relative!=0){
   box->fill.x=((WP(renderer,0x34)>>1)*box->x)/100;
   box->fill.y=((WP(renderer,0x38)>>1)*box->y)/100;
  }else{
   box->fill.x=*(s16 *)&box->x;
   box->fill.y=*(s16 *)&box->y;
  }
  GsSortBoxFill(&box->fill,OT(renderer),box->depth);
  return;
 }
 if((kind&0xFF)!=0x44){
  GsGetLws(BP(object,0x14),lightp,viewp);
  GsSetLightMatrix(lightp);
  GsSetLsMatrix(viewp);
  if(WP(object,0x18)!=0)func_80018464(object+0x10,OT(renderer),0xE - WP(renderer,0x3C),(void *)0x1F800000);
  return;
 }
 {
  vec3d_t position;
  if((kind&0xFFF)==0x144){
   sort_screen_t *screen;
   s32 *screen_dimensions;
   screen=(sort_screen_t *)object;
   sprite=&screen->sprite;
   screen_dimensions=(s32 *)(renderer+0x34);
   sprite->x=screen->percentage_x!=0?((screen_dimensions[0]>>1)*100)/(10000/screen->percentage_x):0;
   sprite->y=screen->percentage_y!=0?((screen_dimensions[1]>>1)*100)/(10000/screen->percentage_y):0;
   sprite->x+=sprite->mx;
   sprite->y+=sprite->my;
   GsSortSprite(sprite,OT(renderer),0);
    return;
  }
  GsGetLs(BP(object,0x14),viewp);
  if((u32)(viewp->vector.z-1)>0xFFFE)return;
  if(WP(BP(object,0xC),0xC)!=0){
   func_8001EE98(&position,BP(object,0x14)+0x18,1,viewp);
   position.x+=view.vector.x;
   position.y+=view.vector.y;
   position.z+=view.vector.z;
  }else position=view.vector;
  if(position.z<=WP(renderer,0x4C))return;
  position.x=position.x*WP(renderer,0x40)/position.z;
  position.y=position.y*WP(renderer,0x40)/position.z;
  position.z=(position.z-WP(renderer,0x4C))/WP(renderer,0x98);
  {
   sort_screen_t *perspective=(sort_screen_t *)object;
   if((position.x>=0?position.x:~position.x+1)<0x201)perspective->sprite.x=position.x;
   else perspective->sprite.x=0x200;
   if((position.y>=0?position.y:~position.y+1)<0x201)perspective->sprite.y=position.y;
   else perspective->sprite.y=0x200;
   GsSortSprite(&perspective->sprite,OT(renderer),position.z);
   return;
  }
 }
}
